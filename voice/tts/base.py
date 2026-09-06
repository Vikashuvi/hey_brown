from abc import ABC, abstractmethod
from typing import Tuple, Generator
import numpy as np


class TTSProvider(ABC):
    """Abstract interface for Text-To-Speech engines."""

    @abstractmethod
    def synthesize(self, text: str) -> Tuple[np.ndarray, int]:
        """Synthesize text to audio.
        Returns:
            Tuple of (audio_samples: np.ndarray, sample_rate: int)
        """
        pass
