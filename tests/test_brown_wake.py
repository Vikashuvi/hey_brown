import numpy as np
from voice.wake.brown_wake_provider import BrownWakeWordProvider


class MockSTT:
    def __init__(self, return_text: str = ""):
        self.return_text = return_text
        self.call_count = 0

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        self.call_count += 1
        return self.return_text


def test_brown_wake_provider_detects_wake_word():
    mock_stt = MockSTT("Hey Brown")
    provider = BrownWakeWordProvider(stt_provider=mock_stt, min_speech_ms=80, silence_timeout_ms=80)
    provider.start()

    # Generate synthetic speech frame (high energy sinusoid)
    t = np.linspace(0, 0.08, 1280, False)
    speech_frame = (np.sin(t * 300 * 2 * np.pi) * 0.5).astype(np.float32)
    silence_frame = np.zeros(1280, dtype=np.float32)

    # 1. Feed speech (3 frames = 240ms)
    for _ in range(3):
        assert provider.process_frame(speech_frame) is None

    # 2. Feed silence to close utterance (3 frames = 240ms)
    detected = None
    for _ in range(3):
        res = provider.process_frame(silence_frame)
        if res:
            detected = res

    assert detected == "hey_brown"
    assert mock_stt.call_count == 1


def test_brown_wake_provider_ignores_unrelated_speech():
    mock_stt = MockSTT("What is the time right now")
    provider = BrownWakeWordProvider(stt_provider=mock_stt, min_speech_ms=80, silence_timeout_ms=80)
    provider.start()

    t = np.linspace(0, 0.08, 1280, False)
    speech_frame = (np.sin(t * 300 * 2 * np.pi) * 0.5).astype(np.float32)
    silence_frame = np.zeros(1280, dtype=np.float32)

    for _ in range(3):
        assert provider.process_frame(speech_frame) is None

    detected = None
    for _ in range(3):
        res = provider.process_frame(silence_frame)
        if res:
            detected = res

    assert detected is None
    assert mock_stt.call_count == 1


def test_brown_wake_custom_phrase():
    mock_stt = MockSTT("Wake up Brown daddy is home")
    provider = BrownWakeWordProvider(
        stt_provider=mock_stt,
        trigger_phrases=["daddy is home", "wake up brown"],
        min_speech_ms=80,
        silence_timeout_ms=80
    )
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

    assert detected == "hey_brown"
    assert mock_stt.call_count == 1
