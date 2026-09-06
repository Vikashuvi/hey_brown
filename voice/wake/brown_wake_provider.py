from typing import Optional, List
import time
import numpy as np
from voice.wake.base import WakeWordProvider
from voice.vad.silero_vad import SileroVADProvider
from voice.stt.base import STTProvider


class BrownWakeWordProvider(WakeWordProvider):
    """Dedicated wake-word detector specifically designed to wake on 'Hey Brown' or 'Brown'.
    
    Architecture:
    - Runs continuous ultra-low-CPU Silero VAD scanning (<1% CPU) on 80ms chunks while idle.
    - Only when a short speech utterance (0.3s - 1.8s) finishes, it runs local fast STT
      on the isolated utterance to check for 'brown' or 'hey brown'.
    - If detected, instantly yields 'hey_brown'.
    - Zero cloud dependencies, 100% private, runs entirely on-device.
    """

    DEFAULT_TRIGGER_PHRASES = [
        "brown", "hey brown", "wake up brown", "daddy is home", "hello brown", "yo brown"
    ]

    def __init__(
        self,
        stt_provider: STTProvider,
        trigger_phrases: Optional[List[str]] = None,
        vad_threshold: float = 0.5,
        min_speech_ms: int = 240,
        silence_timeout_ms: int = 240,
        max_utterance_ms: int = 3000,
    ):
        self.stt_provider = stt_provider
        raw_phrases = trigger_phrases or self.DEFAULT_TRIGGER_PHRASES
        # Normalize triggers to lowercase stripped
        self.trigger_phrases = [p.lower().strip() for p in raw_phrases]
        self.vad_provider = SileroVADProvider(threshold=vad_threshold)
        self.min_speech_frames = max(2, int(min_speech_ms / 80))
        self.silence_timeout_frames = max(2, int(silence_timeout_ms / 80))
        self.max_utterance_frames = int(max_utterance_ms / 80)

        self._running = False
        self._speech_buffer: List[np.ndarray] = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speech_active = False

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
        """Process 1280-sample frame (80ms at 16kHz)."""
        if not self._running:
            self.start()

        # Check voice activity on chunk
        is_speech = self.vad_provider.is_speech(frame, sample_rate=16000)

        if is_speech:
            self._is_speech_active = True
            self._speech_frames += 1
            self._silence_frames = 0
            self._speech_buffer.append(frame)

            # Cap max utterance to avoid runaway buffer if background noise persists
            if len(self._speech_buffer) >= self.max_utterance_frames:
                return self._evaluate_buffer()

        else:
            if self._is_speech_active:
                self._silence_frames += 1
                self._speech_buffer.append(frame)

                # Trailing silence reached: user finished the short wake word phrase
                if self._silence_frames >= self.silence_timeout_frames:
                    if self._speech_frames >= self.min_speech_frames:
                        return self._evaluate_buffer()
                    else:
                        # Spurious click/pop too short to be speech
                        self.reset()

        return None

    def _evaluate_buffer(self) -> Optional[str]:
        """Transcribe isolated micro-buffer and check for 'brown'."""
        if not self._speech_buffer:
            self.reset()
            return None

        audio_data = np.concatenate(self._speech_buffer)
        self.reset()

        try:
            transcript = self.stt_provider.transcribe(audio_data, sample_rate=16000).strip().lower()
            if not transcript:
                return None

            # Strip punctuation
            clean_text = "".join(c for c in transcript if c.isalnum() or c.isspace())

            # Check for configured wake phrases
            for trigger in self.trigger_phrases:
                if trigger in clean_text:
                    return "hey_brown"

        except Exception as e:
            # Silently ignore evaluation glitch in wake loop
            pass

        return None
