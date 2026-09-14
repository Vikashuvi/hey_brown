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
    Supports instant cancellation on user barge-in and sequential clause streaming.
    """

    def __init__(self, device: Optional[int] = None):
        self._device = device
        self._is_playing = False
        self._interrupted = threading.Event()
        self._current_stream = None
        self._lock = threading.Lock()
        self._play_thread: Optional[threading.Thread] = None
        self._clause_queue: queue.Queue = queue.Queue()
        self._current_playback_rms = 0.0
        self._last_playback_write_time = 0.0

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def current_playback_rms(self) -> float:
        """Returns the instantaneous RMS energy of audio actively being sent to the hardware speaker."""
        with self._lock:
            if not self._is_playing or (time.time() - self._last_playback_write_time > 0.25):
                return 0.0
            return self._current_playback_rms

    def interrupt(self) -> bool:
        """Immediately flag interruption, abort audio output, and purge pending clauses."""
        with self._lock:
            self._interrupted.set()
            self._current_playback_rms = 0.0
            # Drain any pending queued clauses
            while not self._clause_queue.empty():
                try:
                    self._clause_queue.get_nowait()
                except Exception:
                    break

            if self._current_stream is not None:
                try:
                    self._current_stream.abort()
                except Exception:
                    pass
                self._current_stream = None
            elif sd is not None:
                try:
                    sd.stop()
                except Exception:
                    pass

            was_playing = self._is_playing
            self._is_playing = False
            return was_playing

    def queue_clause(self, audio_data: np.ndarray, sample_rate: int):
        """Append a synthesized clause to the active playback stream."""
        if not self._interrupted.is_set():
            self._clause_queue.put((audio_data, sample_rate))

    def end_stream(self):
        """Signal that no more clauses will arrive for the current turn."""
        self._clause_queue.put(None)

    def play_clause_stream(
        self,
        on_first_audio: Optional[Callable[[], None]] = None,
        on_complete: Optional[Callable[[], None]] = None
    ) -> bool:
        """Play sequentially queued clauses in real time with instant interruption."""
        self.interrupt()  # Cancel any previous session

        with self._lock:
            self._interrupted.clear()
            self._is_playing = True

        def _stream_worker():
            first_audio_marked = False
            try:
                while not self._interrupted.is_set():
                    try:
                        item = self._clause_queue.get(timeout=4.0)
                    except queue.Empty:
                        break

                    if item is None:
                        # End of stream sentinel reached
                        break

                    audio_data, sample_rate = item
                    if self._interrupted.is_set():
                        break

                    if not first_audio_marked:
                        first_audio_marked = True
                        if on_first_audio:
                            on_first_audio()

                    self._play_raw_chunk(audio_data, sample_rate)

            except Exception as e:
                print(f"[InterruptibleAudioPlayer] Stream error: {e}")
            finally:
                with self._lock:
                    was_interrupted = self._interrupted.is_set()
                    self._is_playing = False
                if not was_interrupted and on_complete:
                    on_complete()

        self._play_thread = threading.Thread(target=_stream_worker, daemon=True)
        self._play_thread.start()
        return True

    def play(self, audio_data: np.ndarray, sample_rate: int, on_complete: Optional[Callable[[], None]] = None) -> bool:
        """Play single audio chunk asynchronously with interruption checking."""
        if sd is None:
            print("[InterruptibleAudioPlayer] sounddevice not available, simulating playback.")
            duration = len(audio_data) / max(sample_rate, 1)
            time.sleep(min(duration, 0.5))
            if on_complete:
                on_complete()
            return True

        self.interrupt()

        with self._lock:
            self._interrupted.clear()
            self._is_playing = True

        def _worker():
            try:
                self._play_raw_chunk(audio_data, sample_rate)
            except Exception as e:
                print(f"[InterruptibleAudioPlayer] Playback error: {e}")
            finally:
                with self._lock:
                    was_interrupted = self._interrupted.is_set()
                    self._is_playing = False
                if not was_interrupted and on_complete:
                    on_complete()

        self._play_thread = threading.Thread(target=_worker, daemon=True)
        self._play_thread.start()
        return True

    def _play_raw_chunk(self, audio_data: np.ndarray, sample_rate: int):
        """Internal low-latency chunk player with immediate abort checking."""
        data = audio_data.astype(np.float32)
        if data.ndim > 1:
            data = data.flatten()

        try:
            dev_info = sd.query_devices(self._device, kind="output")
            native_sr = int(dev_info.get("default_samplerate", sample_rate))
            max_ch = int(dev_info.get("max_output_channels", 1))
        except Exception:
            native_sr = sample_rate
            max_ch = 1

        if sample_rate == 24000 and native_sr == 48000:
            data = np.repeat(data, 2)
            target_sr = 48000
        else:
            target_sr = sample_rate

        if max_ch >= 2:
            data = np.column_stack([data, data])
            channels = 2
        else:
            channels = 1

        chunk_size = 2048
        total_frames = len(data)

        try:
            with sd.OutputStream(
                samplerate=target_sr,
                channels=channels,
                dtype="float32",
                device=self._device,
                blocksize=0
            ) as stream:
                with self._lock:
                    self._current_stream = stream

                idx = 0
                while idx < total_frames and not self._interrupted.is_set():
                    chunk = data[idx : idx + chunk_size]
                    chunk_rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                    with self._lock:
                        self._current_playback_rms = chunk_rms
                        self._last_playback_write_time = time.time()

                    stream.write(chunk)
                    idx += len(chunk)

                if self._interrupted.is_set():
                    try:
                        stream.abort()
                    except Exception:
                        pass
        except Exception:
            # Fallback to high-level sd.play
            try:
                chunk_rms = float(np.sqrt(np.mean(data ** 2))) if len(data) > 0 else 0.0
                with self._lock:
                    self._current_playback_rms = chunk_rms
                    self._last_playback_write_time = time.time()
                sd.play(data, target_sr, device=self._device)
                duration = total_frames / max(target_sr, 1)
                start_t = time.time()
                while (time.time() - start_t) < duration and not self._interrupted.is_set():
                    time.sleep(0.03)
                if self._interrupted.is_set():
                    sd.stop()
            except Exception as fe:
                print(f"[InterruptibleAudioPlayer] Playback fallback failed: {fe}")
        finally:
            with self._lock:
                self._current_stream = None
                self._current_playback_rms = 0.0
