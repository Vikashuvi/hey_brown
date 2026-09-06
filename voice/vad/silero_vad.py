import os
import urllib.request
from typing import Optional
import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None

from voice.vad.base import VADProvider


class SileroVADProvider(VADProvider):
    """Silero VAD (ONNX) provider for low-latency Voice Activity Detection.
    Runs locally on CPU in <1ms per frame.
    """

    SILERO_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"

    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5):
        self.threshold = threshold
        self.model_path = model_path or os.path.expanduser("~/.cache/brown/models/silero_vad.onnx")
        self._session = None
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)
        self._sample_rate = 16000

    def _ensure_model(self):
        if self._session is not None:
            return
        if ort is None:
            return  # Will use fallback energy VAD if onnxruntime not installed

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        if not os.path.exists(self.model_path):
            print(f"[SileroVAD] Downloading Silero VAD ONNX model to {self.model_path}...")
            urllib.request.urlretrieve(self.SILERO_URL, self.model_path)

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._session = ort.InferenceSession(self.model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def is_speech(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        """Determines if the chunk contains speech.
        Expects float32 mono audio chunk (e.g. 512 samples for 32ms at 16kHz).
        """
        try:
            self._ensure_model()
        except Exception as e:
            print(f"[SileroVAD] Error initializing Silero model: {e}. Using fallback energy detector.")

        # Fallback to RMS energy if model is not loaded
        if self._session is None:
            energy = np.sqrt(np.mean(np.square(audio_chunk)))
            return bool(energy > 0.015)

        # Pad or slice to 512 samples if needed for Silero v4
        chunk = audio_chunk.astype(np.float32)
        if len(chunk) < 512:
            chunk = np.pad(chunk, (0, 512 - len(chunk)))
        elif len(chunk) > 512:
            chunk = chunk[:512]

        chunk = chunk[np.newaxis, :]  # Shape: (1, 512)
        sr = np.array(sample_rate, dtype=np.int64)

        try:
            inputs = {
                "input": chunk,
                "sr": sr,
                "h": self._h,
                "c": self._c
            }
            out, self._h, self._c = self._session.run(None, inputs)
            probability = float(out[0][0])
            return probability >= self.threshold
        except Exception as e:
            # On shape mismatch or older model version, fallback to energy check
            energy = np.sqrt(np.mean(np.square(audio_chunk)))
            return bool(energy > 0.015)
