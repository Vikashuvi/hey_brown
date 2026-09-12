import os
import json
import pytest
from core.settings import load_settings, save_settings, DEFAULT_SETTINGS, SETTINGS_FILE

def test_settings_load_defaults():
    settings = load_settings()
    assert isinstance(settings, dict)
    assert settings["assistantName"] == "Brown" or isinstance(settings["assistantName"], str)
    assert "primaryColor" in settings
    assert "wakePhrases" in settings

def test_settings_save_and_reload(tmp_path, monkeypatch):
    test_file = str(tmp_path / "test_settings.json")
    monkeypatch.setattr("core.settings.SETTINGS_FILE", test_file)

    custom = {
        "assistantName": "Jarvis",
        "primaryColor": "#06b6d4",
        "sleepTimeoutSeconds": 15
    }
    success = save_settings(custom)
    assert success is True

    loaded = load_settings()
    assert loaded["assistantName"] == "Jarvis"
    assert loaded["primaryColor"] == "#06b6d4"
    assert loaded["sleepTimeoutSeconds"] == 15
    # Default fields preserved
    assert loaded["glossyEffect"] is True
