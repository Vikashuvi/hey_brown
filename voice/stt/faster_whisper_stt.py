from typing import Optional
import numpy as np

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

from voice.stt.base import STTProvider


class FasterWhisperSTT(STTProvider):
    """Local Speech-to-Text provider powered by faster-whisper (CTranslate2).
    Runs fast on multicore Intel CPU with int8 quantization.
    """

    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8", threads: int = 4):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.threads = threads
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return
        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed.")

        print(f"[FasterWhisperSTT] Loading model '{self.model_size}' on {self.device} ({self.compute_type})...")
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.threads
        )

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe float32 16kHz audio array."""
        self._ensure_model()

        audio = audio_data.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.flatten()

        segments, info = self._model.transcribe(
            audio,
            beam_size=1,
            language="en",
            vad_filter=False  # We do VAD externally before calling STT
        )
        text = " ".join(seg.text for seg in segments).strip()
        return text
