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
        """Immediately flag interruption so worker thread safely stops audio."""
        with self._lock:
            if not self._is_playing:
                return False
            self._interrupted.set()
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

                # Query device native capabilities to prevent macOS AUHAL -10851 errors
                try:
                    dev_info = sd.query_devices(self._device, kind="output")
                    native_sr = int(dev_info.get("default_samplerate", sample_rate))
                    max_ch = int(dev_info.get("max_output_channels", 1))
                except Exception:
                    native_sr = sample_rate
                    max_ch = 1

                # If 24kHz Kokoro audio playing on 48kHz hardware (e.g. MacBook Pro), 2x upsample
                if sample_rate == 24000 and native_sr == 48000:
                    data = np.repeat(data, 2)
                    target_sr = 48000
                else:
                    target_sr = sample_rate

                # If hardware is stereo, duplicate mono to stereo
                if max_ch >= 2:
                    data = np.column_stack([data, data])
                    channels = 2
                else:
                    channels = 1

                # Blocksize 1024 provides ~42ms audio blocks for near-instant abort
                chunk_size = 1024
                total_frames = len(data)

                with sd.OutputStream(
                    samplerate=target_sr,
                    channels=channels,
                    dtype="float32",
                    device=self._device,
                    blocksize=chunk_size
                ) as stream:
                    with self._lock:
                        self._current_stream = stream

                    idx = 0
                    while idx < total_frames and not self._interrupted.is_set():
                        chunk = data[idx : idx + chunk_size]
                        stream.write(chunk)
                        idx += len(chunk)

                    if self._interrupted.is_set():
                        try:
                            stream.abort()
                        except Exception:
                            pass

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
