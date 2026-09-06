from typing import Optional, List
import numpy as np

try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
except Exception:
    OWWModel = None

from voice.wake.base import WakeWordProvider


class OpenWakeWordProvider(WakeWordProvider):
    """Dedicated continuous wake-word detector using openWakeWord (ONNX).
    Runs with very low CPU (<1%) on 1280-sample chunks (80ms).
    STT is NOT activated until this detector confirms a wake trigger.
    """

    def __init__(self, model_names: Optional[List[str]] = None, threshold: float = 0.5):
        self.model_names = model_names or ["hey_jarvis"]
        self.threshold = threshold
        self._model = None

    def start(self):
        if self._model is not None:
            return
        if OWWModel is None:
            raise RuntimeError("openwakeword is not installed.")

        # Download target pre-trained model if needed
        openwakeword.utils.download_models(model_names=self.model_names)
        self._model = OWWModel(
            wakeword_models=self.model_names,
            inference_framework="onnx"
        )

    def stop(self):
        self._model = None

    def reset(self):
        if self._model:
            self._model.reset()

    def process_frame(self, frame: np.ndarray) -> Optional[str]:
        """Process 1280 samples (80ms of 16kHz audio).
        Input can be float32 in [-1, 1] or int16.
        """
        if self._model is None:
            self.start()

        # openWakeWord expects 16-bit PCM integer values
        if frame.dtype != np.int16:
            frame_int16 = (np.clip(frame, -1.0, 1.0) * 32767.0).astype(np.int16)
        else:
            frame_int16 = frame

        # Predict
        prediction = self._model.predict(frame_int16)

        for model_name, score in prediction.items():
            if score >= self.threshold:
                self.reset()
                return model_name

        return None
