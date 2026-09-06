from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class VADProvider(ABC):
    """Abstract interface for Voice Activity Detection."""

    @abstractmethod
    def is_speech(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        """Returns True if the audio chunk contains human voice activity."""
        pass

    @abstractmethod
    def reset(self):
        """Reset internal VAD states (recurrent states)."""
        pass
