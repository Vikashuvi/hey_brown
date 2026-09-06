import threading
import queue
import time
from typing import Optional, Callable
import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

from voice.audio.base import AudioOutput


class InterruptibleAudioPlayer(AudioOutput):
    """Interruptible audio player for TTS playback with immediate hardware buffer abort.
    Supports instant cancellation on user barge-in.
    """

    def __init__(self, device: Optional[int] = None):
        self._device = device
        self._is_playing = False
        self._interrupted = threading.Event()
        self._current_stream = None
        self._lock = threading.Lock()
        self._play_thread: Optional[threading.Thread] = None

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def interrupt(self) -> bool:
        """Immediately abort audio playback and clear buffers."""
        with self._lock:
            if not self._is_playing:
                return False

            self._interrupted.set()
            if self._current_stream:
                try:
                    self._current_stream.abort()
                    self._current_stream.close()
                except Exception:
                    pass
                self._current_stream = None

            self._is_playing = False
            return True

    def play(self, audio_data: np.ndarray, sample_rate: int, on_complete: Optional[Callable[[], None]] = None) -> bool:
        """Play audio asynchronously in chunks with interruption checking."""
        if sd is None:
            print("[InterruptibleAudioPlayer] sounddevice not available, simulating playback.")
            duration = len(audio_data) / max(sample_rate, 1)
            time.sleep(min(duration, 0.5))
            if on_complete:
                on_complete()
            return True

        self.interrupt()  # Cancel any previous playing audio

        with self._lock:
            self._interrupted.clear()
            self._is_playing = True

        def _worker():
            try:
                # Ensure float32 array
                data = audio_data.astype(np.float32)
                if data.ndim > 1:
                    data = data.flatten()

                chunk_size = 2048
                total_frames = len(data)

                with sd.OutputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                    device=self._device,
                    blocksize=chunk_size
                ) as stream:
                    with self._lock:
                        self._current_stream = stream

                    idx = 0
                    while idx < total_frames and not self._interrupted.is_set():
                        chunk = data[idx : idx + chunk_size]
                        # If the last chunk is smaller than chunk_size, pad or write directly
                        stream.write(chunk)
                        idx += len(chunk)

                with self._lock:
                    self._current_stream = None
                    was_interrupted = self._interrupted.is_set()
                    self._is_playing = False

                if not was_interrupted and on_complete:
                    on_complete()

            except Exception as e:
                with self._lock:
                    self._current_stream = None
                    self._is_playing = False
                print(f"[InterruptibleAudioPlayer] Playback error: {e}")

        self._play_thread = threading.Thread(target=_worker, daemon=True)
        self._play_thread.start()
        return True
