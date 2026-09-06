import os
import urllib.request
from typing import Tuple, Optional
import numpy as np

try:
    from kokoro_onnx import Kokoro
except Exception:
    Kokoro = None

from voice.tts.base import TTSProvider


class KokoroTTS(TTSProvider):
    """Local, warm human voice TTS provider powered by Kokoro-82M (ONNX).
    Synthesizes speech on CPU in ~200ms.
    """

    MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
    VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"

    def __init__(self, voice: str = "af_bella", model_dir: Optional[str] = None):
        self.voice = voice
        self.model_dir = model_dir or os.path.expanduser("~/.cache/brown/models/kokoro")
        self.model_path = os.path.join(self.model_dir, "kokoro-v0_19.onnx")
        self.voices_path = os.path.join(self.model_dir, "voices.bin")
        self._kokoro = None

    def _ensure_model(self):
        if self._kokoro is not None:
            return
        if Kokoro is None:
            raise RuntimeError("kokoro-onnx is not installed.")

        os.makedirs(self.model_dir, exist_ok=True)
        if not os.path.exists(self.model_path):
            print(f"[KokoroTTS] Downloading Kokoro model to {self.model_path}...")
            urllib.request.urlretrieve(self.MODEL_URL, self.model_path)

        if not os.path.exists(self.voices_path):
            print(f"[KokoroTTS] Downloading Kokoro voices to {self.voices_path}...")
            urllib.request.urlretrieve(self.VOICES_URL, self.voices_path)

        print("[KokoroTTS] Initializing Kokoro engine...")
        self._kokoro = Kokoro(self.model_path, self.voices_path)

    def synthesize(self, text: str) -> Tuple[np.ndarray, int]:
        self._ensure_model()
        samples, sample_rate = self._kokoro.create(
            text,
            voice=self.voice,
            speed=1.0,
            lang="en-us"
        )
        return samples, sample_rate
