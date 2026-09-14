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
    "wakeThreshold": 0.5,
    "wakeCooldownSeconds": 2.0,
    "wakeCalibrationMode": False,
    "speakerVerification": False,
    "primaryColor": "#7c3aed",
    "eyeColor": "#0f0926",
    "mascotSize": 110,
    "glossyEffect": True,
    "sleepTimeoutSeconds": 8,
    "speechCadenceMs": 300,
    "dialogueMode": "necessary_only",
    "bargeInEnabled": False,
    # Intelligence settings
    "localAiEnabled": True,
    "localAiProvider": "local",
    "localAiModel": "qwen3-vl:2b",
    "localAiVisionModel": "qwen3-vl:2b",
    "localAiUrl": "http://error-boy.local:8765",

    "localAiContextLength": 4096,
    "localAiTemperature": 0.2,
    "localAiKeepWarm": True,
    "localAiAutoStart": True,
    "localAiAutoWarm": True,
    "localAiKeepAliveMinutes": 15,
    "localAiIdleUnload": True,
    "cloudAiEnabled": False,
    "cloudAiProvider": "gemini",
    "cloudAiModel": "gemini-flash-latest",
    "cloudAiVisionModel": "gemini-flash-latest",
    "cloudFallbackEnabled": False,
    "geminiApiKey": "",
    "openaiApiKey": "",
    "privacyMode": "local_only",      # "local_only" | "private" | "normal"
    "routingMode": "local_first",      # "local_first" | "deterministic_first" | "cloud_first"
    "visionRouting": "auto",          # "auto" | "local_only" | "cloud_only"
    # Dynamic Remote Node & Device Configuration
    "remoteNodeEnabled": True,
    "remoteNodeId": "remote_node",
    "remoteNodeName": "Remote Node",
    "remoteNodeUrl": "http://error-boy.local:8765",
    "remoteNodeAuthToken": "",
    "remoteNodeAliases": ["remote", "secondary", "linux", "victus", "error boy", "error_boy"],
    "remoteNodeTimeout": 2.0,
    # Generic Device Registry & AI Inference Routing
    "localInferenceDeviceId": None,  # Dynamically resolved by capabilities if None
    "localInferenceRuntime": "ollama",  # "ollama" | "llamacpp" | "openai_compatible"
    "allowedTransferDirs": ["~/Downloads/BrownTransfers"],
    "maxClipboardSizeBytes": 524288,      # 512 KB
    "maxFileTransferSizeBytes": 52428800,  # 50 MB
}


def load_settings() -> Dict[str, Any]:
    """Load settings from JSON, returning defaults for any missing fields."""
    with _lock:
        if not os.path.exists(SETTINGS_FILE):
            merged = dict(DEFAULT_SETTINGS)
            if os.environ.get("GEMINI_API_KEY"):
                merged["geminiApiKey"] = os.environ["GEMINI_API_KEY"].strip().rstrip(".")
            if os.environ.get("OPENAI_API_KEY"):
                merged["openaiApiKey"] = os.environ["OPENAI_API_KEY"].strip()
            return merged

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)

                # Sync environment variables for cloud AI providers
                if merged.get("geminiApiKey"):
                    os.environ["GEMINI_API_KEY"] = merged["geminiApiKey"].strip().rstrip(".")
                elif os.environ.get("GEMINI_API_KEY"):
                    merged["geminiApiKey"] = os.environ["GEMINI_API_KEY"].strip().rstrip(".")

                if merged.get("openaiApiKey"):
                    os.environ["OPENAI_API_KEY"] = merged["openaiApiKey"].strip()
                elif os.environ.get("OPENAI_API_KEY"):
                    merged["openaiApiKey"] = os.environ["OPENAI_API_KEY"].strip()

                return merged
        except Exception as e:
            print(f"[Settings] Error reading {SETTINGS_FILE}: {e}, using defaults.")
            merged = dict(DEFAULT_SETTINGS)
            if os.environ.get("GEMINI_API_KEY"):
                merged["geminiApiKey"] = os.environ["GEMINI_API_KEY"].strip().rstrip(".")
            if os.environ.get("OPENAI_API_KEY"):
                merged["openaiApiKey"] = os.environ["OPENAI_API_KEY"].strip()
            return merged


def save_settings(settings: Dict[str, Any]) -> bool:
    """Validate and persist settings to JSON file."""
    with _lock:
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(settings)

            # Sync active environment variables
            if merged.get("geminiApiKey"):
                os.environ["GEMINI_API_KEY"] = merged["geminiApiKey"].strip().rstrip(".")
            if merged.get("openaiApiKey"):
                os.environ["OPENAI_API_KEY"] = merged["openaiApiKey"].strip()
            
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


# Alias for load_settings
get_settings = load_settings
