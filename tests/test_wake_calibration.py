"""Tests for Two-Stage Wake Detection, Phonetic Variations, and Calibration Mode."""

import time
import numpy as np
from voice.wake.brown_wake_provider import BrownWakeWordProvider


class MockSTT:
    def __init__(self, text: str = ""):
        self.text = text

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        return self.text


def test_wake_phonetic_variant_detection():
    """Verify phonetic variants like 'braun', 'hey bro', 'broun' trigger wake correctly."""
    variants = ["braun", "hey braun", "hey bro", "broun", "wake brown"]

    for variant in variants:
        mock_stt = MockSTT(variant)
        provider = BrownWakeWordProvider(stt_provider=mock_stt, threshold=0.5, min_speech_ms=80, silence_timeout_ms=80, cooldown_sec=0.0)
        provider.start()

        t = np.linspace(0, 0.08, 1280, False)
        speech_frame = (np.sin(t * 300 * 2 * np.pi) * 0.5).astype(np.float32)
        silence_frame = np.zeros(1280, dtype=np.float32)

        for _ in range(3):
            provider.process_frame(speech_frame)

        detected = None
        for _ in range(3):
            res = provider.process_frame(silence_frame)
            if res:
                detected = res

        assert detected == "hey_brown", f"Failed for phonetic variant '{variant}'"


def test_wake_cooldown_prevention():
    """Verify cooldown timer prevents immediate double wake activation."""
    mock_stt = MockSTT("Hey Brown")
    provider = BrownWakeWordProvider(stt_provider=mock_stt, threshold=0.5, min_speech_ms=80, silence_timeout_ms=80, cooldown_sec=2.0)
    provider.start()

    t = np.linspace(0, 0.08, 1280, False)
    speech_frame = (np.sin(t * 300 * 2 * np.pi) * 0.5).astype(np.float32)
    silence_frame = np.zeros(1280, dtype=np.float32)

    # First activation
    for _ in range(3):
        provider.process_frame(speech_frame)
    detected1 = None
    for _ in range(3):
        res = provider.process_frame(silence_frame)
        if res:
            detected1 = res
    assert detected1 == "hey_brown"

    # Immediate second utterance within 2.0s cooldown must be suppressed
    for _ in range(3):
        provider.process_frame(speech_frame)
    detected2 = None
    for _ in range(3):
        res = provider.process_frame(silence_frame)
        if res:
            detected2 = res
    assert detected2 is None, "Cooldown failed to suppress repeated activation"


def test_wake_calibration_telemetry():
    """Verify calibration mode fires diagnostic telemetry payloads."""
    diagnostics = []

    def handle_diagnostic(data):
        diagnostics.append(data)

    mock_stt = MockSTT("Hey Brown")
    provider = BrownWakeWordProvider(
        stt_provider=mock_stt,
        threshold=0.5,
        calibration_mode=True,
        on_diagnostic=handle_diagnostic
    )
    provider.start()

    t = np.linspace(0, 0.08, 1280, False)
    speech_frame = (np.sin(t * 300 * 2 * np.pi) * 0.5).astype(np.float32)

    provider.process_frame(speech_frame)
    assert len(diagnostics) > 0
    diag = diagnostics[-1]
    assert "wake_phrase" in diag
    assert "detection_score" in diag
    assert "threshold" in diag
    assert "vad_state" in diag
