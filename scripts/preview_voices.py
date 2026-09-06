"""Voice Preview & Selector for Brown AI Assistant.

Lists and plays all available hyper-realistic local Kokoro-82M voices.
"""

import os
import sys
import time
import sounddevice as sd

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice.tts.kokoro_tts import KokoroTTS
from voice.audio.player import InterruptibleAudioPlayer

VOICE_CATALOG = {
    "1": ("af_bella", "American Female — Expressive, warm conversational tone (Selected)"),
    "2": ("af_sarah", "American Female — Professional, clear narrator style"),
    "3": ("af_sky", "American Female — Bright, casual, natural tone"),
    "4": ("af_nicole", "American Female — Calm, whisper-smooth tone"),
    "5": ("bf_emma", "British Female — Posh, articulate, clear"),
    "6": ("bf_isabella", "British Female — Gentle, warm cadence"),
    "7": ("bm_george", "British Male — Calm, distinguished, butler style"),
    "8": ("bm_lewis", "British Male — Crisp, younger cadence"),
    "9": ("am_adam", "American Male — Deep, natural, clear conversational tone"),
    "10": ("am_michael", "American Male — Friendly, upbeat assistant tone"),
}


def main():
    print("\n" + "=" * 65)
    print(" 🎙️ BROWN AI ASSISTANT — VOICE PREVIEW & SELECTOR")
    print("=" * 65 + "\n")
    print("Select a voice to listen to a preview:\n")

    for key, (voice_id, desc) in VOICE_CATALOG.items():
        print(f" [{key:>2}] {voice_id:<12} — {desc}")

    print(" [all] Play all voices one after another")
    print(" [q]   Quit\n")

    tts = KokoroTTS()
    player = InterruptibleAudioPlayer()

    while True:
        choice = input("Enter voice number to preview (or 'q' to quit): ").strip().lower()
        if choice in ("q", "quit", "exit"):
            break

        if choice == "all":
            for k, (v_id, d) in VOICE_CATALOG.items():
                print(f"\n▶️ Playing [{v_id}]: {d}...")
                tts.voice = v_id
                phrase = f"Hello Vikash. This is {v_id}. How does my voice sound to you?"
                samples, sr = tts.synthesize(phrase)
                player.play(samples, sr)
                while player.is_playing:
                    time.sleep(0.05)
                time.sleep(0.5)
            print("\nFinished previewing all voices!")
            continue

        if choice in VOICE_CATALOG:
            v_id, d = VOICE_CATALOG[choice]
            print(f"\n▶️ Playing [{v_id}]: {d}...")
            tts.voice = v_id
            phrase = f"Hello Vikash! I am Brown using the {v_id} voice. All systems are operational."
            samples, sr = tts.synthesize(phrase)
            player.play(samples, sr)
            while player.is_playing:
                time.sleep(0.05)
            print("Finished playback.")
            print(f"👉 To use this voice permanently, set 'voice: \"{v_id}\"' in config/default.yaml\n")
        else:
            print("Invalid choice. Please enter a number between 1 and 10.")


if __name__ == "__main__":
    main()
