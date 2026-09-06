import numpy as np
from voice.vad.silero_vad import SileroVADProvider


def test_vad_silence_vs_speech():
    vad = SileroVADProvider(threshold=0.5)

    # 1. Pure silence (zeros)
    silence = np.zeros(512, dtype=np.float32)
    assert not vad.is_speech(silence, sample_rate=16000)

    # 2. Low-amplitude background noise (RMS << 0.015) - False wake resistance
    low_noise = np.random.normal(0, 0.001, 512).astype(np.float32)
    assert not vad.is_speech(low_noise, sample_rate=16000)

    # 3. Speech-like active audio frame (high energy burst)
    t = np.linspace(0, 0.032, 512, False)
    speech_frame = (np.sin(t * 300 * 2 * np.pi) * 0.4).astype(np.float32)
    assert vad.is_speech(speech_frame, sample_rate=16000)
