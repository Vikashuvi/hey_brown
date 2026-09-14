"""Unit test suite for Phase B & C: Local AI Runtime Abstraction and Lifecycle."""

import pytest
from unittest.mock import patch, MagicMock
from core.ai.runtime import LocalInferenceRuntime, OllamaRuntime, OpenAICompatibleRuntime, create_local_runtime
from core.ai.local_provider import LocalAIProvider
from core.device_resolver import DeviceResolver, DeviceRecord
from core.ai.base import ChatMessage


def test_runtime_factory():
    r1 = create_local_runtime("ollama", "http://localhost:11434")
    assert isinstance(r1, OllamaRuntime)
    assert r1.name == "ollama"

    r2 = create_local_runtime("llamacpp", "http://localhost:8080")
    assert isinstance(r2, OpenAICompatibleRuntime)
    assert r2.name == "openai_compatible"

    r3 = create_local_runtime("openai_compatible", "http://192.168.1.100:8000")
    assert isinstance(r3, OpenAICompatibleRuntime)


def test_ollama_runtime_chat_mock():
    runtime = OllamaRuntime("http://mock-ollama:11434")
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "message": {"content": "Hello from mock Ollama!"}
        }

        resp = runtime.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="qwen2.5:1.5b"
        )
        assert resp.content == "Hello from mock Ollama!"
        assert resp.provider == "local"
        assert resp.model == "qwen2.5:1.5b"


def test_ollama_runtime_lifecycle():
    runtime = OllamaRuntime("http://mock-ollama:11434")
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        assert runtime.warm_model("qwen2.5:1.5b", keep_alive="10m") is True
        assert runtime.unload_model("qwen2.5:1.5b") is True


def test_local_provider_dynamic_device_resolution():
    custom_devices = {
        "workstation": DeviceRecord(
            id="workstation",
            display_name="Inference Rig",
            connection_url="http://192.168.1.99:11434",
            capabilities=["local_llm"],
            roles=["inference_node"]
        )
    }
    resolver = DeviceResolver(custom_devices)
    provider = LocalAIProvider(
        device_resolver=resolver,
        preferred_device_id="workstation",
        model="qwen3-vl:2b"
    )

    assert provider.active_device_id == "workstation"
    assert provider.base_url == "http://192.168.1.99:11434"

    # Offline health state should report the resolved workstation device
    health = provider.get_health_state()
    assert health["device"] == "workstation"
    assert health["ready"] is False
    assert health["state"] == "OFFLINE"
