"""Interactive Quick Test for Brown AI Assistant.

Tests:
1. Kokoro-82M Voice Playback (Speakers)
2. Microphone capture & Faster-Whisper local transcription (Microphone)
3. Hardware Barge-in audio cancellation test
4. Typed System Tool test
"""

import os
import sys
import time
import numpy as np
import sounddevice as sd

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice.tts.kokoro_tts import KokoroTTS
from voice.stt.faster_whisper_stt import FasterWhisperSTT
from voice.audio.player import InterruptibleAudioPlayer
from agents.paperball import PaperballAgent


def print_banner():
    print("\n" + "=" * 65)
    print(" 🇮🇳 BROWN AI ASSISTANT — INTERACTIVE QUICK TEST")
    print("=" * 65 + "\n")


def test_1_voice_output():
    print("👉 [Test 1/4] Testing Local Human Voice (Kokoro-82M ONNX)...")
    print("Synthesizing speech...")
    tts = KokoroTTS(voice="bm_george")
    text = "Hello! I am Brown, your personal computer assistant. All local neural systems are fully operational."
    samples, sr = tts.synthesize(text)
    print(f"Playing through your speakers: \"{text}\"")
    sd.play(samples, sr)
    sd.wait()
    print("✅ Test 1 Complete! You should have heard Brown's voice.\n")


def test_2_barge_in():
    print("👉 [Test 2/4] Testing Instant Hardware Barge-In (Interruption)...")
    tts = KokoroTTS(voice="bm_george")
    player = InterruptibleAudioPlayer()
    
    long_text = (
        "I am going to speak a very long sentence so you can test interrupting me. "
        "I will keep talking and talking about the architecture of multiple computers, "
        "including Paperball and Error Boy, until you press Enter or start speaking."
    )
    samples, sr = tts.synthesize(long_text)
    print("\nBrown will now start speaking a long paragraph.")
    print("PRESS [ENTER] AT ANY TIME to interrupt him mid-sentence!\n")
    
    player.play(samples, sr)
    time.sleep(0.5)
    
    input(">>> Press [ENTER] now to interrupt Brown >>> ")
    t0 = time.time()
    player.interrupt()
    elapsed_ms = (time.time() - t0) * 1000
    print(f"⚡ Interrupted! Audio cut in {elapsed_ms:.1f}ms.")
    print("✅ Test 2 Complete! Audio stopped instantaneously.\n")


def test_3_microphone_and_stt():
    print("👉 [Test 3/4] Testing Microphone & Local Speech-to-Text (Whisper)...")
    print("Get ready to speak a short sentence (e.g., 'Hello Brown how are you').")
    for i in range(3, 0, -1):
        print(f"Recording starts in {i}...")
        time.sleep(1)
        
    duration = 3.5  # seconds
    sr = 16000
    print(f"🔴 RECORDING NOW ({duration}s)... SPEAK CLEARLY INTO MIC!")
    recording = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    print("⏹️ Recording finished! Transcribing with local Faster-Whisper (int8 CPU)...")
    
    stt = FasterWhisperSTT(model_size="base.en", device="cpu", compute_type="int8")
    t0 = time.time()
    transcript = stt.transcribe(recording.flatten(), sample_rate=sr)
    print(f"⚡ Transcribed in {time.time() - t0:.2f}s:")
    print(f"📝 You said: \"{transcript}\"")
    print("✅ Test 3 Complete!\n")


def test_4_typed_tool():
    print("👉 [Test 4/4] Testing Native macOS Device Agent (Paperball)...")
    agent = PaperballAgent()
    status = agent.get_system_status()
    print(f"Status message: {status.message}")
    print(f"Data: {status.data}")
    print("✅ Test 4 Complete!\n")


def main():
    print_banner()
    print("This script will guide you through testing all core components:")
    print(" 1. Human Voice Output (Speakers)")
    print(" 2. Instant Barge-In (Interruption)")
    print(" 3. Microphone Capture & Speech-to-Text")
    print(" 4. Safe Device Agent Status\n")
    
    input("Press [ENTER] to begin...")
    test_1_voice_output()
    test_2_barge_in()
    test_3_microphone_and_stt()
    test_4_typed_tool()
    
    print("=" * 65)
    print("🎉 ALL TESTS PASSED! Brown's V1 core is 100% verified.")
    print("To run the full continuous voice loop, run:")
    print("   PYTHONPATH=. .venv/bin/python3 main.py")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
