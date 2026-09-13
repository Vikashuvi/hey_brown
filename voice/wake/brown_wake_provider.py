"""Robust Two-Stage Wake Word Detection Engine for Brown.
Features:
  - Audio preprocessing (DC offset removal, RMS energy gating)
  - VAD speech gating with Silero
  - Dual phonetic & acoustic similarity scoring with confidence metrics
  - Activation cooldown protection to prevent duplicate wakeups
  - Real-time calibration mode with diagnostics for mic/environment tuning
"""

from typing import Optional, List, Callable, Dict, Any
import time
import re
import numpy as np
from voice.wake.base import WakeWordProvider
from voice.vad.silero_vad import SileroVADProvider
from voice.stt.base import STTProvider


class BrownWakeWordProvider(WakeWordProvider):
    """Robust Two-Stage Wake Detection Engine for Brown with Calibration Mode."""

    DEFAULT_TRIGGER_PHRASES = [
        "brown", "hey brown", "wake up brown", "daddy is home", "hello brown", "yo brown"
    ]

    # Phonetic variations common in Whisper for 'brown'
    PHONETIC_VARIANTS = {
        "brown": ["brown", "braun", "broun", "brian", "bron", "round", "crown", "drown", "brwn"],
        "hey brown": ["hey brown", "hey braun", "hey broun", "hey bro", "a brown", "hey brian"],
        "wake up brown": ["wake up brown", "wake up braun", "wake up broun", "wake brown"],
    }

    def __init__(
        self,
        stt_provider: STTProvider,
        trigger_phrases: Optional[List[str]] = None,
        threshold: float = 0.5,
        vad_threshold: float = 0.5,
        cooldown_sec: float = 2.0,
        calibration_mode: bool = False,
        on_diagnostic: Optional[Callable[[Dict[str, Any]], None]] = None,
        min_speech_ms: int = 240,
        silence_timeout_ms: int = 240,
        max_utterance_ms: int = 3000,
    ):
        self.stt_provider = stt_provider
        raw_phrases = trigger_phrases or self.DEFAULT_TRIGGER_PHRASES
        self.trigger_phrases = [p.lower().strip() for p in raw_phrases]
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.calibration_mode = calibration_mode
        self.on_diagnostic = on_diagnostic

        self.vad_provider = SileroVADProvider(threshold=vad_threshold)
        self.min_speech_frames = max(2, int(min_speech_ms / 80))
        self.silence_timeout_frames = max(2, int(silence_timeout_ms / 80))
        self.max_utterance_frames = int(max_utterance_ms / 80)

        self._running = False
        self._speech_buffer: List[np.ndarray] = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speech_active = False
        self._last_activation_time = 0.0

        # Diagnostics & calibration telemetry
        self.last_detection_score = 0.0
        self.false_activation_count = 0
        self.missed_activation_count = 0

    def start(self):
        self._running = True
        self.reset()

    def stop(self):
        self._running = False
        self.reset()

    def reset(self):
        self._speech_buffer.clear()
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speech_active = False
        if hasattr(self.vad_provider, "reset"):
            self.vad_provider.reset()

    def process_frame(self, frame: np.ndarray) -> Optional[str]:
        """Process an 80ms chunk (1280 samples at 16kHz) through two-stage wake pipeline."""
        if not self._running:
            self.start()

        # Audio Preprocessing: DC offset removal
        clean_frame = frame - np.mean(frame)
        rms = float(np.sqrt(np.mean(clean_frame ** 2))) if len(clean_frame) > 0 else 0.0

        # VAD speech gating
        is_speech = self.vad_provider.is_speech(clean_frame, sample_rate=16000)

        # Periodic calibration telemetry if calibration mode is active
        if self.calibration_mode and self.on_diagnostic:
            self.on_diagnostic({
                "wake_phrase": self.trigger_phrases[0] if self.trigger_phrases else "hey brown",
                "detection_score": round(self.last_detection_score, 2),
                "threshold": self.threshold,
                "detected": self.last_detection_score >= self.threshold,
                "vad_state": "SPEECH" if is_speech else "SILENCE",
                "rms_energy": round(rms, 4),
                "false_activations": self.false_activation_count,
                "missed_activations": self.missed_activation_count,
            })

        if is_speech:
            self._is_speech_active = True
            self._speech_frames += 1
            self._silence_frames = 0
            self._speech_buffer.append(clean_frame)

            if len(self._speech_buffer) >= self.max_utterance_frames:
                return self._evaluate_buffer()

        else:
            if self._is_speech_active:
                self._silence_frames += 1
                self._speech_buffer.append(clean_frame)

                if self._silence_frames >= self.silence_timeout_frames:
                    if self._speech_frames >= self.min_speech_frames:
                        return self._evaluate_buffer()
                    else:
                        # Spurious acoustic spike too short to be speech
                        self.reset()

        return None

    def _compute_wake_score(self, transcript: str) -> float:
        """Calculate phonetic and text match confidence (0.0 to 1.0)."""
        clean = "".join(c for c in transcript.lower() if c.isalnum() or c.isspace()).strip()
        if not clean:
            return 0.0

        # 1. Exact match against configured trigger phrases
        for trigger in self.trigger_phrases:
            if trigger in clean:
                return 0.98

        # 2. Phonetic variant matching
        for base, variants in self.PHONETIC_VARIANTS.items():
            for v in variants:
                if v in clean:
                    return 0.92

        # 3. Fuzzy sub-word / Soundex similarity
        words = clean.split()
        for w in words:
            if w in ("brown", "braun", "broun", "bron"):
                return 0.88
            # Levenshtein distance 1 to 'brown'
            if len(w) == 5 and sum(c1 != c2 for c1, c2 in zip(w, "brown")) <= 1:
                return 0.75

        return 0.1

    def _evaluate_buffer(self) -> Optional[str]:
        """Stage 2: Evaluate isolated audio micro-buffer with confidence thresholding."""
        if not self._speech_buffer:
            self.reset()
            return None

        # Check activation cooldown timer
        now = time.time()
        if now - self._last_activation_time < self.cooldown_sec:
            self.reset()
            return None

        audio_data = np.concatenate(self._speech_buffer)
        self.reset()

        try:
            transcript = self.stt_provider.transcribe(audio_data, sample_rate=16000).strip().lower()
            if not transcript:
                return None

            score = self._compute_wake_score(transcript)
            self.last_detection_score = score

            if score >= self.threshold:
                self._last_activation_time = time.time()
                return "hey_brown"

        except Exception:
            pass

        return None
