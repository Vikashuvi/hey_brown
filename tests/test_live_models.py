import numpy as np
from voice.wake.openwakeword_provider import OpenWakeWordProvider
from voice.tts.kokoro_tts import KokoroTTS
from voice.stt.faster_whisper_stt import FasterWhisperSTT


def test_openwakeword_loads_and_evaluates():
    provider = OpenWakeWordProvider(model_names=["hey_jarvis"], threshold=0.5)
    provider.start()

    # Silence frame should not trigger
    silence = np.zeros(1280, dtype=np.float32)
    assert provider.process_frame(silence) is None

    # Noise frame should not trigger
    noise = np.random.uniform(-0.05, 0.05, 1280).astype(np.float32)
    assert provider.process_frame(noise) is None

    provider.stop()


def test_kokoro_and_whisper_roundtrip():
    # 1. Synthesize text with Kokoro
    tts = KokoroTTS(voice="bm_george")
    samples, sr = tts.synthesize("Brown is online.")
    assert len(samples) > 0
    assert sr == 24000

    # 2. Downsample to 16kHz for Whisper
    import scipy.signal
    num_samples = int(len(samples) * 16000 / sr)
    resampled = scipy.signal.resample(samples, num_samples).astype(np.float32)

    # 3. Transcribe with Whisper
    stt = FasterWhisperSTT(model_size="base.en", device="cpu", compute_type="int8")
    transcript = stt.transcribe(resampled, sample_rate=16000)
    assert "brown" in transcript.lower() or "online" in transcript.lower()
