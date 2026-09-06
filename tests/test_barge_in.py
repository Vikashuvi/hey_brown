import time
import numpy as np
from voice.audio.player import InterruptibleAudioPlayer


def test_player_interrupt_aborts_playback():
    player = InterruptibleAudioPlayer()

    # Generate 2 seconds of synthetic sine wave audio at 16000 Hz
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    sine_wave = (np.sin(t * 440 * 2 * np.pi) * 0.2).astype(np.float32)

    completed = []

    def on_complete():
        completed.append(True)

    # Start playback
    player.play(sine_wave, sample_rate, on_complete=on_complete)
    assert player.is_playing

    # Wait 100ms then trigger barge-in interrupt
    time.sleep(0.1)
    interrupted = player.interrupt()
    assert interrupted
    assert not player.is_playing

    # Verify that playback did NOT complete cleanly
    time.sleep(0.2)
    assert len(completed) == 0


def test_player_completes_naturally_when_uninterrupted():
    player = InterruptibleAudioPlayer()

    # Very short 50ms chirp
    sample_rate = 16000
    duration = 0.05
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    chirp = (np.sin(t * 440 * 2 * np.pi) * 0.1).astype(np.float32)

    completed = []

    def on_complete():
        completed.append(True)

    player.play(chirp, sample_rate, on_complete=on_complete)
    
    # Wait for completion (up to 1.5s)
    timeout = 1.5
    start = time.time()
    while player.is_playing and time.time() - start < timeout:
        time.sleep(0.05)

    assert not player.is_playing
    assert len(completed) == 1
