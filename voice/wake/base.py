from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np


class WakeWordProvider(ABC):
    """Abstract base class for dedicated continuous wake-word detectors.
    Processes small audio frames (typically 16kHz int16 or float32 PCM)
    with low CPU overhead without activating STT.
    """

    @abstractmethod
    def start(self):
        """Initialize and prepare the wake-word detector."""
        pass

    @abstractmethod
    def stop(self):
        """Clean up and release resources."""
        pass

    @abstractmethod
    def process_frame(self, frame: np.ndarray) -> Optional[str]:
        """Process an audio frame.
        Returns:
            Wake word label (e.g. 'hey_brown') if detected, otherwise None.
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset internal acoustic history/state."""
        pass
