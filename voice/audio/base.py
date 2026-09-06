from abc import ABC, abstractmethod
from typing import Generator, Optional, Callable
import numpy as np


class AudioInput(ABC):
    """Abstract interface for audio capture."""

    @abstractmethod
    def start(self):
        """Start capturing audio."""
        pass

    @abstractmethod
    def stop(self):
        """Stop capturing audio."""
        pass

    @abstractmethod
    def read_chunk(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Read a single chunk of audio frames (int16 or float32)."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        pass


class AudioOutput(ABC):
    """Abstract interface for interruptible audio playback."""

    @abstractmethod
    def play(self, audio_data: np.ndarray, sample_rate: int, on_complete: Optional[Callable[[], None]] = None) -> bool:
        """Start playback of audio data asynchronously."""
        pass

    @abstractmethod
    def interrupt(self) -> bool:
        """Immediately halt playback and discard any queued audio chunks."""
        pass

    @property
    @abstractmethod
    def is_playing(self) -> bool:
        """Return True if currently outputting audio."""
        pass
