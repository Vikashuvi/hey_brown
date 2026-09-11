import time
import asyncio
import sys
from core.events import get_event_bridge

def main():
    bridge = get_event_bridge()
    bridge.start()
    print("UIEventBridge started on ws://127.0.0.1:8766. Waiting 1.5s for Brown.app to connect...")
    time.sleep(1.5)

    print("--> Broadcasting WAKE_DETECTED (Overlay should appear near top-right!)...")
    bridge.broadcast("state_change", {"state": "WAKE_DETECTED"})
    time.sleep(2.0)

    print("--> Broadcasting LISTENING...")
    bridge.broadcast("state_change", {"state": "LISTENING"})
    bridge.broadcast("transcript", {"text": "What time is it?"})
    time.sleep(2.0)

    print("--> Broadcasting SPEAKING...")
    bridge.broadcast("state_change", {"state": "SPEAKING"})
    bridge.broadcast("tts_speaking", {"speaking": True, "text": "It is currently 10:05 PM."})
    time.sleep(3.0)

    print("--> Broadcasting HAPPY (celebrate!)...")
    bridge.broadcast("tts_speaking", {"speaking": False})
    bridge.broadcast("state_change", {"state": "HAPPY"})
    time.sleep(2.0)

    print("--> Broadcasting SLEEPING (Overlay will smoothly fade away into menu bar)...")
    bridge.broadcast("state_change", {"state": "SLEEPING"})
    time.sleep(1.5)

    bridge.stop()
    print("Test finished!")

if __name__ == "__main__":
    main()
