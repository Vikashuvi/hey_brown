"""Conversational Intelligence Layer for Brown using PydanticAI.

Implements Brown's conversational reasoning, bounded context handling,
typed tool calling, dynamic persona synthesis, and grounded verification.
PydanticAI serves as an internal library component; Brown's core orchestrator,
device agents, security, and verification remain authoritative.
"""

import os
import time
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.messages import ModelMessage

from core.conversation import ConversationContext
from core.device_resolver import DeviceResolver
from tools.base import ToolRegistry, ToolResult
from core.privacy import PrivacyFilter

logger = logging.getLogger("brown.brain")

# Ensure PydanticAI startup banner doesn't clutter logs/voice stream
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


BROWN_SYSTEM_PROMPT = """You are Brown, an intelligent, personal computer assistant and voice agent.
You manage two primary machines:
- "paperball": the local host machine (macOS).
- "error_boy": the secondary remote machine (Arch Linux laptop with NVIDIA GPU).

Core personality & spoken response guidelines:
1. Speak naturally, concisely, and directly in 1 to 2 spoken sentences. Avoid long monologues unless specifically asked for a list or explanation.
2. Never recite robotic boilerplate (e.g. do not say "I have successfully executed the tool").
3. Ground your answers strictly in the verified facts and data returned by tools. Never invent or hallucinate metrics, status, or outcomes.
4. If a tool reports that a device or service is unreachable or offline, state it clearly (e.g. "Error Boy is currently offline or unreachable."). Do not guess or make up data for an offline machine.
5. For pure conversation, greetings, jokes, or conceptual questions, reply naturally without calling tools.
6. When resolving follow-ups (e.g. "what about the RAM?", "can you run it?", "check the other laptop", "do that again"), use the active device, entity, and last action provided in context.
"""


@dataclass
class BrainDeps:
    """Authoritative dependencies injected into every PydanticAI tool call."""
    device_resolver: DeviceResolver
    tool_registry: ToolRegistry
    context: ConversationContext
    devices: Dict[str, Any]
    settings: Dict[str, Any]
    privacy_mode: str = "local_only"
    event_bridge: Optional[Any] = None

    # Turn execution telemetry
    last_tool_called: Optional[str] = None
    last_tool_args: Optional[Dict[str, Any]] = None
    last_tool_result: Optional[Dict[str, Any]] = None
    last_target_device: Optional[str] = None
    last_tool_success: bool = True


class BrainResponse(BaseModel):
    """Structured result from conversational reasoning."""
    text: str
    tool_called: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    target_device: str = "paperball"
    success: bool = True
    latency_ms: float = 0.0
    fallback_used: bool = False


def create_pydantic_agent(model: Optional[Model] = None) -> Agent[BrainDeps, str]:
    """Instantiate the PydanticAI Agent with typed system tools."""
    agent = Agent(
        model=model or TestModel(),
        deps_type=BrainDeps,
        output_type=str,
        system_prompt=BROWN_SYSTEM_PROMPT,
    )

    @agent.system_prompt
    def dynamic_context_prompt(ctx: RunContext[BrainDeps]) -> str:
        summary = ctx.deps.context.build_prompt_context()
        return f"\nActive Conversation State: {summary}"

    @agent.tool
    def get_system_status(
        ctx: RunContext[BrainDeps],
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves CPU, RAM, and health status for a target device ('paperball' or 'error_boy')."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "get_system_status"
        ctx.deps.last_tool_args = {"device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("get_system_status")
        if not tool:
            res = {"success": False, "error": "System status tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(device=dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)

        res_dict = {
            "success": result.success,
            "device": dev,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def get_running_apps(
        ctx: RunContext[BrainDeps],
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves the list of running applications from a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "get_running_apps"
        ctx.deps.last_tool_args = {"device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("get_running_apps")
        if not tool:
            res = {"success": False, "error": "Running apps tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(device=dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)

        res_dict = {
            "success": result.success,
            "device": dev,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def open_application(
        ctx: RunContext[BrainDeps],
        app_name: str,
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Safely launches an application on a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "open_application"
        ctx.deps.last_tool_args = {"app_name": app_name, "device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("open_application")
        if not tool:
            res = {"success": False, "error": "Open app tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(app_name=app_name, device=dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)
        ctx.deps.context.active_app = app_name
        ctx.deps.context.update_entity("app", app_name)

        res_dict = {
            "success": result.success,
            "device": dev,
            "app_name": app_name,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def close_application(
        ctx: RunContext[BrainDeps],
        app_name: str,
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Safely closes or quits an application on a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "close_application"
        ctx.deps.last_tool_args = {"app_name": app_name, "device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("close_application")
        if not tool:
            res = {"success": False, "error": "Close app tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(app_name=app_name, device=dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)

        res_dict = {
            "success": result.success,
            "device": dev,
            "app_name": app_name,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def open_url(
        ctx: RunContext[BrainDeps],
        url: str,
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Opens a web URL in the default browser on a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "open_url"
        ctx.deps.last_tool_args = {"url": url, "device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("open_url")
        if not tool:
            res = {"success": False, "error": "Open URL tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(url=url, device=dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)
        ctx.deps.context.update_entity("url", url)

        res_dict = {
            "success": result.success,
            "device": dev,
            "url": url,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def get_local_ai_status(
        ctx: RunContext[BrainDeps],
        target_device: Optional[str] = "remote_node",
        model: Optional[str] = "qwen3-vl:2b"
    ) -> Dict[str, Any]:
        """Checks if the local AI / LLM model is loaded in memory and running on the target machine."""
        dev = ctx.deps.device_resolver.resolve(target_device or "remote_node")
        ctx.deps.last_tool_called = "get_local_ai_status"
        ctx.deps.last_tool_args = {"device": dev, "model": model}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("get_local_ai_status")
        if not tool:
            res = {"success": False, "error": "Local AI status tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(device=dev, model=model or "qwen3-vl:2b")
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)
        if model:
            ctx.deps.context.update_entity("model", model)

        res_dict = {
            "success": result.success,
            "device": dev,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def manage_local_ai(
        ctx: RunContext[BrainDeps],
        action: str = "warm",
        target_device: Optional[str] = "remote_node",
        model: Optional[str] = "qwen3-vl:2b"
    ) -> Dict[str, Any]:
        """Starts, warms, or unloads the local AI model on the designated machine."""
        dev = ctx.deps.device_resolver.resolve(target_device or "remote_node")
        ctx.deps.last_tool_called = "manage_local_ai"
        ctx.deps.last_tool_args = {"action": action, "device": dev, "model": model}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("manage_local_ai")
        if not tool:
            res = {"success": False, "error": "Manage local AI tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(action=action, device=dev, model=model or "qwen3-vl:2b")
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)
        if model:
            ctx.deps.context.update_entity("model", model)

        res_dict = {
            "success": result.success,
            "device": dev,
            "action": action,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def get_device_capabilities(
        ctx: RunContext[BrainDeps],
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves typed capabilities and hardware features of a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "get_device_capabilities"
        ctx.deps.last_tool_args = {"device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("get_device_capabilities")
        if not tool:
            res = {"success": False, "error": "Capabilities tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(device=dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dev)

        res_dict = {
            "success": result.success,
            "device": dev,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    return agent


class BrownBrain:
    """Conversational reasoning engine for Brown.
    
    Orchestrates natural dialogue, tool routing, grounded verification,
    and conversational continuity without bypassing device security.
    """

    def __init__(
        self,
        device_resolver: DeviceResolver,
        tool_registry: ToolRegistry,
        devices: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None,
        model: Optional[Model] = None,
        context: Optional[ConversationContext] = None,
        event_bridge: Optional[Any] = None,
    ):
        self.device_resolver = device_resolver
        self.tool_registry = tool_registry
        self.devices = devices
        self.settings = settings or {}
        self.context = context or ConversationContext()
        self.event_bridge = event_bridge
        self.privacy_mode = self.settings.get("privacyMode", "local_only")

        self.model = model or self._resolve_model()
        self.agent = create_pydantic_agent(self.model)
        self._history_messages: List[ModelMessage] = []

    def _resolve_model(self) -> Model:
        """Construct the appropriate PydanticAI model from configuration."""
        local_ai_enabled = self.settings.get("localAiEnabled", True)
        local_ai_url = self.settings.get("localAiUrl", "http://10.217.30.46:8765")
        local_model_name = self.settings.get("localAiModel", "qwen3-vl:2b")
        cloud_ai_enabled = self.settings.get("cloudAiEnabled", False)
        gemini_key = self.settings.get("geminiApiKey") or os.environ.get("GEMINI_API_KEY")

        # 1. Local Model via OpenAI-compatible endpoint
        if local_ai_enabled:
            try:
                import httpx
                from openai import AsyncOpenAI
                base_url = f"{local_ai_url.rstrip('/')}/v1"
                client = AsyncOpenAI(
                    base_url=base_url,
                    api_key="ollama",
                    max_retries=0,
                    timeout=httpx.Timeout(connect=2.0, read=25.0, write=5.0, pool=2.0)
                )
                provider = OpenAIProvider(openai_client=client)
                return OpenAIChatModel(local_model_name, provider=provider)
            except Exception as e:
                logger.warning(f"[BrownBrain] Could not initialize local model: {e}")

        # 2. Cloud Model (Gemini) if permitted by privacy mode
        if cloud_ai_enabled and PrivacyFilter.check_cloud_allowed(self.privacy_mode) and gemini_key:
            try:
                os.environ.setdefault("GEMINI_API_KEY", gemini_key)
                from pydantic_ai.models.google import GoogleModel
                cloud_model_name = self.settings.get("cloudAiModel", "gemini-1.5-flash")
                return GoogleModel(cloud_model_name)
            except Exception as ce:
                logger.warning(f"[BrownBrain] Could not initialize cloud model: {ce}")

        # Fallback to TestModel
        return TestModel()

    def process_query(self, query: str) -> BrainResponse:
        """Process a natural language user query with conversational context & tools."""
        t0 = time.time()
        self.context.prune_expired()

        deps = BrainDeps(
            device_resolver=self.device_resolver,
            tool_registry=self.tool_registry,
            context=self.context,
            devices=self.devices,
            settings=self.settings,
            privacy_mode=self.privacy_mode,
            event_bridge=self.event_bridge,
        )

        try:
            run_result = self.agent.run_sync(
                query,
                deps=deps,
                message_history=self._history_messages,
            )

            # Keep bounded history (last 10 messages)
            self._history_messages.extend(run_result.new_messages())
            if len(self._history_messages) > 10:
                self._history_messages = self._history_messages[-10:]

            spoken_text = run_result.output
            latency_ms = round((time.time() - t0) * 1000, 2)

            # Record turn in bounded context
            target_device = deps.last_target_device or self.context.active_device
            self.context.record_turn(
                user_query=query,
                response_text=spoken_text,
                tool_name=deps.last_tool_called,
                tool_args=deps.last_tool_args,
                tool_result=deps.last_tool_result,
                success=deps.last_tool_success,
                verified=True if deps.last_tool_called else False,
                device=target_device,
            )

            return BrainResponse(
                text=spoken_text,
                tool_called=deps.last_tool_called,
                tool_args=deps.last_tool_args,
                tool_result=deps.last_tool_result,
                target_device=target_device,
                success=deps.last_tool_success,
                latency_ms=latency_ms,
                fallback_used=False,
            )

        except Exception as e:
            latency_ms = round((time.time() - t0) * 1000, 2)
            logger.error(f"[BrownBrain] Error processing query: {e}", exc_info=True)

            # Graceful error response
            fallback_text = "I encountered an issue processing that request. Please try again."
            if "Connection" in str(e) or "unreachable" in str(e).lower():
                fallback_text = "I'm having trouble connecting to the local AI service."

            return BrainResponse(
                text=fallback_text,
                target_device=self.context.active_device,
                success=False,
                latency_ms=latency_ms,
                fallback_used=True,
            )

    def reset_history(self):
        """Clear active dialogue history."""
        self._history_messages.clear()
        self.context = ConversationContext()
