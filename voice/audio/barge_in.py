"""Acoustic Barge-In Detector & Echo Protection for Brown Voice Assistant.

Prevents acoustic feedback self-triggering while enabling ultra-fast (<200ms)
interruption when genuine user speech breaks through Brown's audio playback.
"""

import time
import numpy as np
from typing import Optional


class AcousticBargeInDetector:
    """Intelligent barge-in evaluator with dynamic speaker bleed rejection."""

    def __init__(
        self,
        min_interruption_frames: int = 2,    # ~160ms of sustained speech
        bleed_energy_factor: float = 1.3,     # Mic energy must exceed bleed baseline
        min_speech_confidence: float = 0.65,  # VAD probability requirement during playback
        energy_floor: float = 0.015,          # Minimum RMS for human speech
    ):
        self.min_interruption_frames = min_interruption_frames
        self.bleed_energy_factor = bleed_energy_factor
        self.min_speech_confidence = min_speech_confidence
        self.energy_floor = energy_floor

        self.playback_active = False
        self._consecutive_speech_frames = 0
        self._speaker_bleed_rms = 0.01
        self._last_interrupt_time = 0.0

    def set_playback_active(self, active: bool):
        """Update whether Brown's speaker is currently outputting audio."""
        if self.playback_active != active:
            self.playback_active = active
            if not active:
                self._consecutive_speech_frames = 0
                self._speaker_bleed_rms = 0.01

    def evaluate_frame(
        self,
        chunk: np.ndarray,
        is_vad_speech: bool,
        speech_prob: float = 0.8,
        playback_rms: float = 0.0,
    ) -> bool:
        """Evaluates whether an incoming audio frame constitutes a genuine user interruption."""
        if not self.playback_active:
            # When not speaking, barge-in is not applicable
            self._consecutive_speech_frames = 0
            return False

        if chunk is None or len(chunk) == 0:
            return False

        # Compute RMS energy of mic input
        float_chunk = chunk.astype(np.float32)
        if np.max(np.abs(float_chunk)) > 1.0:
            float_chunk /= 32768.0

        rms = float(np.sqrt(np.mean(float_chunk ** 2)))

        # Update running estimate of speaker bleed
        if playback_rms > 0.0:
            bleed_estimate = max(self._speaker_bleed_rms, playback_rms * 0.50)
            self._speaker_bleed_rms = max(
                self._speaker_bleed_rms * 0.85 + rms * 0.15,
                playback_rms * 0.45
            )
        else:
            bleed_estimate = self._speaker_bleed_rms
            if not is_vad_speech or speech_prob < 0.5:
                self._speaker_bleed_rms = 0.85 * self._speaker_bleed_rms + 0.15 * max(rms, 0.005)
                self._consecutive_speech_frames = max(0, self._consecutive_speech_frames - 1)
                return False

        # During playback, verify:
        # 1. VAD indicates speech with sufficient confidence
        # 2. Mic RMS exceeds the estimated speaker bleed baseline AND exceeds minimum human energy floor
        required_energy = max(self.energy_floor, bleed_estimate * self.bleed_energy_factor)
        is_above_bleed = rms >= required_energy
        is_confident = speech_prob >= self.min_speech_confidence

        if is_vad_speech and is_above_bleed and is_confident:
            self._consecutive_speech_frames += 1
            if self._consecutive_speech_frames >= self.min_interruption_frames:
                self._last_interrupt_time = time.time()
                self._consecutive_speech_frames = 0
                return True
        else:
            self._consecutive_speech_frames = max(0, self._consecutive_speech_frames - 1)

        return False

    def reset(self):
        """Reset state tracking."""
        self._consecutive_speech_frames = 0
        self.playback_active = False
