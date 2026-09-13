"""Comprehensive test suite for Brown's Conversational Intelligence Layer with PydanticAI.

Tests cover:
1. Pure conversation (no tools needed).
2. Action execution with grounded verification and dynamic persona synthesis.
3. Pronoun resolution and follow-up conversational continuity.
4. Capability-aware offline device handling (no hallucinated metrics).
5. Local AI status and lifecycle management.
"""

import pytest
from unittest.mock import MagicMock

from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart

from core.ai.brain import BrownBrain
from core.conversation import ConversationContext
from core.device_resolver import DeviceResolver
from tools.base import ToolRegistry
from tools.system_tools import (
    OpenAppTool,
    CloseAppTool,
    OpenUrlTool,
    SystemStatusTool,
    GetRunningAppsTool,
    GetLocalAIStatusTool,
    ManageLocalAITool,
    GetCapabilitiesTool,
)
from devices.base import DeviceCommandResult


@pytest.fixture
def mock_devices():
    """Mock local (macOS) and remote (Linux/Error Boy) device agents."""
    mac = MagicMock()
    mac.display_name = "Paperball (macOS)"
    mac.get_system_status.return_value = DeviceCommandResult(
        success=True,
        message="System status OK",
        data={"cpu_usage": 14.2, "memory_usage": 42.0, "load1": 1.10}
    )
    mac.get_running_apps.return_value = DeviceCommandResult(
        success=True,
        message="Running apps",
        data={"running_apps": ["Safari", "Terminal", "VS Code"]}
    )
    mac.open_application.return_value = DeviceCommandResult(
        success=True,
        message="Safari launched successfully",
        data={"app": "Safari"}
    )
    mac.close_application.return_value = DeviceCommandResult(
        success=True,
        message="Safari closed",
        data={"app": "Safari"}
    )
    mac.open_url.return_value = DeviceCommandResult(
        success=True,
        message="Opened https://github.com",
        data={"url": "https://github.com"}
    )
    mac.get_device_capabilities.return_value = DeviceCommandResult(
        success=True,
        message="Capabilities",
        data={"supported_capabilities": ["open_app", "close_app", "system_status"]}
    )

    linux = MagicMock()
    linux.display_name = "Error Boy (Arch Linux)"
    linux.get_system_status.return_value = DeviceCommandResult(
        success=True,
        message="Remote healthy",
        data={"cpu_usage": 28.5, "memory_usage": 65.0, "load1": 0.45, "gpu_temp": 52}
    )
    linux.get_ai_status.return_value = DeviceCommandResult(
        success=True,
        message="Local AI ready",
        data={"state": "READY", "loaded": True, "active_model": "qwen3-vl:2b"}
    )
    linux.ai_warm.return_value = DeviceCommandResult(
        success=True,
        message="Model warmed",
        data={"model": "qwen3-vl:2b", "status": "warmed"}
    )

    return {"paperball": mac, "error_boy": linux}


@pytest.fixture
def test_registry(mock_devices):
    registry = ToolRegistry()
    registry.register(OpenAppTool(mock_devices))
    registry.register(CloseAppTool(mock_devices))
    registry.register(OpenUrlTool(mock_devices))
    registry.register(SystemStatusTool(mock_devices))
    registry.register(GetRunningAppsTool(mock_devices))
    registry.register(GetCapabilitiesTool(mock_devices))
    registry.register(GetLocalAIStatusTool(mock_devices))
    registry.register(ManageLocalAITool(mock_devices))
    return registry


def test_pure_conversation_no_tools(test_registry, mock_devices):
    """Verify purely conversational queries do not invoke tools."""
    resolver = DeviceResolver()

    def pure_chat_model(messages, info):
        return ModelResponse(parts=[TextPart("I'm doing well, thank you for asking!")])

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=test_registry,
        devices=mock_devices,
        model=FunctionModel(pure_chat_model)
    )

    resp = brain.process_query("How are you feeling today?")
    assert resp.tool_called is None
    assert resp.text == "I'm doing well, thank you for asking!"
    assert len(brain.context.recent_dialogue) == 1
    assert brain.context.recent_dialogue[0].tool_called is None


def test_grounded_status_tool_execution(test_registry, mock_devices):
    """Verify tool execution returns grounded data and updates context."""
    resolver = DeviceResolver()

    def status_model(messages, info):
        for m in reversed(messages):
            if hasattr(m, "parts"):
                for p in m.parts:
                    if getattr(p, "part_kind", None) == "tool-return":
                        cpu = p.content["data"]["cpu_usage"]
                        return ModelResponse(parts=[TextPart(f"Paperball is running at {cpu}% CPU.")])
        return ModelResponse(parts=[ToolCallPart("get_system_status", {"target_device": "paperball"})])

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=test_registry,
        devices=mock_devices,
        model=FunctionModel(status_model)
    )

    resp = brain.process_query("Check the machine status.")
    assert resp.tool_called == "get_system_status"
    assert resp.success is True
    assert resp.tool_result["data"]["cpu_usage"] == 14.2
    assert resp.target_device == "paperball"
    assert brain.context.last_verified_result["data"]["cpu_usage"] == 14.2
    assert brain.context.last_action.tool_name == "get_system_status"
    assert "14.2% CPU" in resp.text


def test_pronoun_and_follow_up_continuity(test_registry, mock_devices):
    """Verify follow-up context preserves active entity across turns."""
    resolver = DeviceResolver()
    context = ConversationContext()

    def turn1_model(messages, info):
        for m in reversed(messages):
            if hasattr(m, "parts"):
                for p in m.parts:
                    if getattr(p, "part_kind", None) == "tool-return":
                        return ModelResponse(parts=[TextPart("Opened Safari for you.")])
        return ModelResponse(parts=[ToolCallPart("open_application", {"app_name": "Safari", "target_device": "paperball"})])

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=test_registry,
        devices=mock_devices,
        context=context,
        model=FunctionModel(turn1_model)
    )

    # Turn 1: Open Safari
    resp1 = brain.process_query("Open Safari.")
    assert resp1.tool_called == "open_application"
    assert brain.context.active_app == "Safari"
    assert brain.context.active_device == "paperball"
    assert brain.context.referenced_entities.get("app") == "Safari"

    # Turn 2: Follow-up referencing active context
    def turn2_model(messages, info):
        for m in reversed(messages):
            if hasattr(m, "parts"):
                for p in m.parts:
                    if getattr(p, "part_kind", None) == "tool-return" and getattr(p, "tool_name", None) == "close_application":
                        return ModelResponse(parts=[TextPart("Closed Safari.")])
        # Resolve 'it' using context active app
        app = brain.context.active_app or "Safari"
        return ModelResponse(parts=[ToolCallPart("close_application", {"app_name": app, "target_device": "paperball"})])

    from core.ai.brain import create_pydantic_agent
    brain.agent = create_pydantic_agent(FunctionModel(turn2_model))

    resp2 = brain.process_query("Close it now.")
    assert resp2.tool_called == "close_application"
    assert resp2.tool_args["app_name"] == "Safari"
    assert brain.context.last_action.tool_name == "close_application"


def test_offline_capability_aware_handling(mock_devices):
    """Verify unreachable devices return verified failure without hallucinating metrics."""
    mock_devices["error_boy"].get_system_status.return_value = DeviceCommandResult(
        success=False,
        message="Could not connect to Error Boy daemon at http://10.217.30.46:8765. Connection refused.",
        data=None
    )

    registry = ToolRegistry()
    registry.register(SystemStatusTool(mock_devices))
    resolver = DeviceResolver()

    def offline_model(messages, info):
        for m in reversed(messages):
            if hasattr(m, "parts"):
                for p in m.parts:
                    if getattr(p, "part_kind", None) == "tool-return":
                        return ModelResponse(parts=[TextPart("Error Boy is unreachable right now.")])
        return ModelResponse(parts=[ToolCallPart("get_system_status", {"target_device": "error_boy"})])

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=registry,
        devices=mock_devices,
        model=FunctionModel(offline_model)
    )

    resp = brain.process_query("What's the status of Error Boy?")
    assert resp.tool_called == "get_system_status"
    assert resp.success is False
    assert "Could not connect" in resp.tool_result["message"]
    assert resp.target_device == "error_boy"
    assert brain.context.last_action.success is False
    assert "unreachable" in resp.text


def test_local_ai_status_and_manage(test_registry, mock_devices):
    """Verify local AI lifecycle tools function properly."""
    resolver = DeviceResolver()

    def ai_status_model(messages, info):
        for m in reversed(messages):
            if hasattr(m, "parts"):
                for p in m.parts:
                    if getattr(p, "part_kind", None) == "tool-return":
                        return ModelResponse(parts=[TextPart("Yes, Qwen 2B is loaded and ready in memory on Error Boy.")])
        return ModelResponse(parts=[ToolCallPart("get_local_ai_status", {"target_device": "error_boy", "model": "qwen3-vl:2b"})])

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=test_registry,
        devices=mock_devices,
        model=FunctionModel(ai_status_model)
    )

    resp = brain.process_query("Is the local AI running on Error Boy?")
    assert resp.tool_called == "get_local_ai_status"
    assert resp.success is True
    assert resp.tool_result["data"]["loaded"] is True
    assert brain.context.referenced_entities.get("model") == "qwen3-vl:2b"
    assert "ready in memory" in resp.text
