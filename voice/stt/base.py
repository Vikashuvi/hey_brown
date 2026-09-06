from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class STTProvider(ABC):
    """Abstract interface for Speech-To-Text engines."""

    @abstractmethod
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe speech audio data into text.
        audio_data is typically float32 mono at 16kHz.
        """
        pass
