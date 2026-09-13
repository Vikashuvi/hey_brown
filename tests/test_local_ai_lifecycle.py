"""Unit and integration tests for Brown Local AI automatic lifecycle management.
Tests LocalAIState transitions, provider status inspection, auto-warming, and unloaded recovery.
"""

import time
import json
import pytest
from unittest.mock import MagicMock, patch

from core.ai.local_provider import LocalAIProvider
from core.ai.base import ChatMessage
from devices.remote_daemon import LocalAIState, get_local_ai_status, _state_lock


def test_local_ai_state_constants():
    """Verify standard granular health state enums."""
    assert LocalAIState.OFFLINE == "OFFLINE"
    assert LocalAIState.STARTING == "STARTING"
    assert LocalAIState.OLLAMA_UNAVAILABLE == "OLLAMA_UNAVAILABLE"
    assert LocalAIState.MODEL_NOT_INSTALLED == "MODEL_NOT_INSTALLED"
    assert LocalAIState.MODEL_LOADING == "MODEL_LOADING"
    assert LocalAIState.READY == "READY"
    assert LocalAIState.BUSY == "BUSY"
    assert LocalAIState.RESOURCE_LIMITED == "RESOURCE_LIMITED"
    assert LocalAIState.ERROR == "ERROR"


def test_get_local_ai_status_resource_constrained():
    """Verify RESOURCE_LIMITED is returned if free RAM is below threshold."""
    with patch("devices.remote_daemon.check_ai_resource_availability") as mock_res:
        mock_res.return_value = (False, "insufficient_resources", {"ram_available_mb": 250.0})
        status = get_local_ai_status("qwen3-vl:2b")
        assert status["state"] == LocalAIState.RESOURCE_LIMITED
        assert status["ready"] is False
        assert status["reason"] == "insufficient_resources"


def test_get_local_ai_status_ollama_unavailable():
    """Verify OLLAMA_UNAVAILABLE returned when Ollama daemon is down."""
    with patch("devices.remote_daemon.check_ai_resource_availability") as mock_res:
        mock_res.return_value = (True, "ready", {"ram_available_mb": 2048.0})
        with patch("devices.remote_daemon.check_ollama_runtime") as mock_ol:
            mock_ol.return_value = (False, [], [])
            with patch("devices.remote_daemon.attempt_ollama_recovery"):
                status = get_local_ai_status("qwen3-vl:2b")
                assert status["state"] in (LocalAIState.OLLAMA_UNAVAILABLE, LocalAIState.STARTING)
                assert status["ready"] is False


def test_get_local_ai_status_model_not_installed():
    """Verify MODEL_NOT_INSTALLED returned when configured model is missing."""
    with patch("devices.remote_daemon.check_ai_resource_availability") as mock_res:
        mock_res.return_value = (True, "ready", {"ram_available_mb": 2048.0})
        with patch("devices.remote_daemon.check_ollama_runtime") as mock_ol:
            mock_ol.return_value = (True, ["llama3:8b"], [])
            status = get_local_ai_status("qwen3-vl:2b")
            assert status["state"] == LocalAIState.MODEL_NOT_INSTALLED
            assert status["ready"] is False


def test_get_local_ai_status_ready_and_loaded():
    """Verify READY returned with accurate loaded boolean."""
    with patch("devices.remote_daemon.check_ai_resource_availability") as mock_res:
        mock_res.return_value = (True, "ready", {"ram_available_mb": 2048.0})
        with patch("devices.remote_daemon.check_ollama_runtime") as mock_ol:
            mock_ol.return_value = (True, ["qwen3-vl:2b"], ["qwen3-vl:2b"])
            status = get_local_ai_status("qwen3-vl:2b")
            assert status["state"] == LocalAIState.READY
            assert status["ready"] is True
            assert status["loaded"] is True


def test_local_provider_get_health_state_offline():
    """Verify LocalAIProvider returns graceful OFFLINE state when endpoint is unreachable."""
    provider = LocalAIProvider(base_url="http://127.0.0.1:9999", model="qwen3-vl:2b")
    state = provider.get_health_state()
    assert state["state"] == "OFFLINE"
    assert state["ready"] is False
    assert state["device"] == "error_boy"


def test_local_provider_warm_model_success():
    """Verify LocalAIProvider.warm_model sends proper JSON to /ai/warm."""
    provider = LocalAIProvider(base_url="http://mock-error-boy:8765", model="qwen3-vl:2b")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "state": "READY", "model": "qwen3-vl:2b"}
        mock_post.return_value = mock_resp

        res = provider.warm_model(keep_alive="15m")
        assert res["success"] is True
        assert res["state"] == "READY"
        mock_post.assert_called_once_with(
            "http://mock-error-boy:8765/ai/warm",
            json={"model": "qwen3-vl:2b", "keep_alive": "15m"},
            timeout=30.0
        )


def test_local_provider_unload_model_success():
    """Verify LocalAIProvider.unload_model sends unload request."""
    provider = LocalAIProvider(base_url="http://mock-error-boy:8765", model="qwen3-vl:2b")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "unloaded": True}
        mock_post.return_value = mock_resp

        res = provider.unload_model()
        assert res["success"] is True
        assert res["unloaded"] is True
        mock_post.assert_called_once_with(
            "http://mock-error-boy:8765/ai/unload",
            json={"model": "qwen3-vl:2b"},
            timeout=5.0
        )
