"""Persistent Settings Manager for Brown AI Assistant.
Manages user customization (name, wake words, colors, timings) with JSON persistence.
Thread-safe and cross-platform compatible.
"""

import json
import os
import threading
from typing import Dict, Any, List

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")
_lock = threading.Lock()

DEFAULT_SETTINGS: Dict[str, Any] = {
    "assistantName": "Brown",
    "wakePhrases": ["hey brown", "brown", "wake up brown"],
    "primaryColor": "#7c3aed",
    "eyeColor": "#0f0926",
    "mascotSize": 110,
    "glossyEffect": True,
    "sleepTimeoutSeconds": 8,
    "speechCadenceMs": 300,
    "dialogueMode": "necessary_only",
    "bargeInEnabled": False
}


def load_settings() -> Dict[str, Any]:
    """Load settings from JSON, returning defaults for any missing fields."""
    with _lock:
        if not os.path.exists(SETTINGS_FILE):
            return dict(DEFAULT_SETTINGS)

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
        except Exception as e:
            print(f"[Settings] Error reading {SETTINGS_FILE}: {e}, using defaults.")
            return dict(DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> bool:
    """Validate and persist settings to JSON file."""
    with _lock:
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(settings)
            
            # Temporary file write for atomic replacement
            temp_file = f"{SETTINGS_FILE}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2)
            os.replace(temp_file, SETTINGS_FILE)
            print(f"[Settings] Saved settings to {SETTINGS_FILE}")
            return True
        except Exception as e:
            print(f"[Settings] Error saving settings: {e}")
            return False
