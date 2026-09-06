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

        # Scan audio chunk in 512-sample windows to cover the full frame
        chunk = audio_chunk.astype(np.float32)
        sr = np.array(sample_rate, dtype=np.int64)
        window_size = 512

        try:
            # Check RMS energy first as a micro-fast filter
            rms = np.sqrt(np.mean(np.square(chunk)))
            if rms < 0.005:
                return False

            num_windows = max(1, (len(chunk) + window_size - 1) // window_size)
            for i in range(num_windows):
                start = i * window_size
                sub_chunk = chunk[start : start + window_size]
                if len(sub_chunk) < window_size:
                    sub_chunk = np.pad(sub_chunk, (0, window_size - len(sub_chunk)))

                sub_input = sub_chunk[np.newaxis, :]
                inputs = {
                    "input": sub_input,
                    "sr": sr,
                    "h": self._h,
                    "c": self._c
                }
                out, self._h, self._c = self._session.run(None, inputs)
                prob = float(out[0][0])
                if prob >= self.threshold:
                    return True

            return False
        except Exception:
            # Fallback to RMS energy if model run fails
            return bool(rms > 0.015)
