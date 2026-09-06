import queue
import time
from typing import Optional
import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

from voice.audio.base import AudioInput


class MicrophoneStream(AudioInput):
    """Captures microphone audio using sounddevice with non-blocking stream."""

    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1280, device: Optional[int] = None):
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._device = device
        self._queue: queue.Queue = queue.Queue(maxsize=100)
        self._stream = None
        self._is_running = False

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    def _audio_callback(self, indata, frames, time_info, status):
        # Extract mono float32 channel directly without redundant copies
        data = indata[:, 0].copy()
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            # If buffer full due to spike, drop oldest frame to prevent latency drift
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(data)
            except Exception:
                pass

    def start(self):
        if self._is_running:
            return
        if sd is None:
            raise RuntimeError("sounddevice is not available.")

        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            blocksize=self._chunk_size,
            device=self._device,
            channels=1,
            dtype="float32",
            callback=self._audio_callback
        )
        self._stream.start()
        self._is_running = True

    def stop(self):
        if not self._is_running:
            return
        self._is_running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def read_chunk(self, timeout: Optional[float] = 0.1) -> Optional[np.ndarray]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self):
        """Drain any lingering queued audio."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
