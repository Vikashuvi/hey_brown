"""Conversational Intelligence Layer for Brown using PydanticAI.

Implements Brown's conversational reasoning, bounded context handling,
typed tool calling, dynamic persona synthesis, and grounded verification.
PydanticAI serves as an internal library component; Brown's core orchestrator,
device agents, security, and verification remain authoritative.
"""

import os
import time
import uuid
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Generator
import threading
from pydantic import BaseModel, Field

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.openai import OpenAIChatModel, _ChatCompletion
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.messages import ModelMessage

from core.conversation import ConversationContext
from core.device_resolver import DeviceResolver
from tools.base import ToolRegistry, ToolResult
from core.privacy import PrivacyFilter
from core.conversation_behavior import ConversationBehaviorLayer, PersonalityProfile
from core.memory.manager import MemoryManager

logger = logging.getLogger("brown.brain")

# Ensure PydanticAI startup banner doesn't clutter logs/voice stream
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


BROWN_SYSTEM_PROMPT = """You are Brown: a personal, persistent AI partner and technical colleague working side-by-side with the user.
You are NOT a generic customer support chatbot. You are an opinionated, intelligent, and capable peer.

Core Persona & Dialogue Directives:
1. Persistent Relationship: Treat dialogue as an ongoing partnership. If you know the user's name, preferences, projects, or past decisions from persistent memory, use them naturally. Never announce "According to my memory" or "I recall that".
2. Directness over Politeness: Answer factual questions immediately ("What's the CPU usage?" -> "About 18%."). Never use introductory filler ("Sure, I can check that for you.").
3. Opinions & Disagreement: You have genuine points of view. When the user shares opinions, critiques, or ideas (e.g. "That's a terrible idea" or "I think this architecture is perfect"), engage directly. Explain why you agree or disagree, challenge faulty assumptions, and suggest better alternatives. NEVER give passive non-answers like "I understand" or "Of course".
4. Absolute Ban on Canned Assistant Openers: NEVER start responses with "Sure", "Certainly", "Absolutely", "Of course", "I'm here", "How can I help?", "What can I do for you?", "I'd be happy to...", or "I can help with that".
5. Conversational Continuity: Short follow-ups ("Why?", "What about this?", "Do it again", "No, the other one", "Are you sure?") inherit full context from previous turns without requiring repetition.
6. Punchy Answers: When appropriate, be brief ("Yeah.", "No.", "Not yet.", "Done.", "It's running.", "Give me a second.", "Actually, no.", "That failed.").
7. Grounding: Ground system status strictly in verified tool outputs. Never invent or hallucinate metrics.
8. Non-Action Conversation: Only invoke tools when an action is explicitly requested. Answer questions, opinions, and banter purely in spoken dialogue.
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
    behavior_layer: Optional[ConversationBehaviorLayer] = None
    memory_manager: Optional[Any] = None
    memory_context: str = ""

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
    target_device: str = "local"
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
    def dynamic_device_prompt(ctx: RunContext[BrainDeps]) -> str:
        dev_summary = ctx.deps.device_resolver.get_devices_prompt_summary()
        return f"\nManaged Devices:\n{dev_summary}"

    @agent.system_prompt
    def dynamic_context_prompt(ctx: RunContext[BrainDeps]) -> str:
        summary = ctx.deps.context.build_prompt_context()
        return f"\nActive Conversation State: {summary}"

    @agent.system_prompt
    def dynamic_behavior_prompt(ctx: RunContext[BrainDeps]) -> str:
        if ctx.deps.behavior_layer:
            return ctx.deps.behavior_layer.build_system_prompt_directives()
        return ""

    @agent.system_prompt
    def dynamic_memory_prompt(ctx: RunContext[BrainDeps]) -> str:
        if ctx.deps.memory_context:
            return f"\n{ctx.deps.memory_context}"
        return ""

    @agent.tool
    def get_system_status(
        ctx: RunContext[BrainDeps],
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves CPU, RAM, and health status for a target device."""
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

    @agent.tool
    def get_clipboard(
        ctx: RunContext[BrainDeps],
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reads text from the clipboard of a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "get_clipboard"
        ctx.deps.last_tool_args = {"device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("get_clipboard")
        if not tool:
            res = {"success": False, "error": "Get clipboard tool unavailable.", "device": dev}
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
    def set_clipboard(
        ctx: RunContext[BrainDeps],
        text: str,
        target_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sets text into the clipboard of a target device."""
        dev = ctx.deps.device_resolver.resolve(target_device or ctx.deps.context.active_device)
        ctx.deps.last_tool_called = "set_clipboard"
        ctx.deps.last_tool_args = {"text": text, "device": dev}
        ctx.deps.last_target_device = dev

        tool = ctx.deps.tool_registry.get("set_clipboard")
        if not tool:
            res = {"success": False, "error": "Set clipboard tool unavailable.", "device": dev}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(text=text, device=dev)
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
    def sync_clipboard(
        ctx: RunContext[BrainDeps],
        from_device: Optional[str] = None,
        to_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronizes/copies clipboard contents from one device to another."""
        src_dev = ctx.deps.device_resolver.resolve(from_device or ctx.deps.device_resolver.default_local_device)
        dst_dev = ctx.deps.device_resolver.resolve(to_device or ctx.deps.device_resolver.default_remote_device)

        ctx.deps.last_tool_called = "sync_clipboard"
        ctx.deps.last_tool_args = {"from_device": src_dev, "to_device": dst_dev}
        ctx.deps.last_target_device = dst_dev

        tool = ctx.deps.tool_registry.get("sync_clipboard")
        if not tool:
            res = {"success": False, "error": "Sync clipboard tool unavailable."}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(from_device=src_dev, to_device=dst_dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dst_dev)
        res_dict = {
            "success": result.success,
            "from_device": src_dev,
            "to_device": dst_dev,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    @agent.tool
    def transfer_file(
        ctx: RunContext[BrainDeps],
        filename: str,
        from_device: Optional[str] = None,
        to_device: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transfers a file from a source device to a target destination device."""
        src_dev = ctx.deps.device_resolver.resolve(from_device or ctx.deps.device_resolver.default_local_device)
        dst_dev = ctx.deps.device_resolver.resolve(to_device or ctx.deps.device_resolver.default_remote_device)

        ctx.deps.last_tool_called = "transfer_file"
        ctx.deps.last_tool_args = {"filename": filename, "from_device": src_dev, "to_device": dst_dev}
        ctx.deps.last_target_device = dst_dev

        tool = ctx.deps.tool_registry.get("transfer_file")
        if not tool:
            res = {"success": False, "error": "Transfer file tool unavailable."}
            ctx.deps.last_tool_result = res
            ctx.deps.last_tool_success = False
            return res

        result = tool.execute(filename=filename, from_device=src_dev, to_device=dst_dev)
        ctx.deps.last_tool_success = result.success
        ctx.deps.context.set_active_device(dst_dev)
        res_dict = {
            "success": result.success,
            "filename": filename,
            "from_device": src_dev,
            "to_device": dst_dev,
            "message": result.message,
            "data": result.data or {}
        }
        ctx.deps.last_tool_result = res_dict
        return res_dict

    return agent


class ResilientLocalOpenAIModel(OpenAIChatModel):
    """Resilient OpenAI Chat Model wrapper for local runtimes and daemons.
    Normalizes missing fields (id, choices, object) so PydanticAI never crashes on non-standard responses.
    """
    def _validate_completion(self, response: Any) -> _ChatCompletion:
        dump = response.model_dump() if hasattr(response, "model_dump") else (response if isinstance(response, dict) else {})

        # If choices is missing or empty, build standard choice structure
        if not dump.get("choices"):
            content = dump.get("content") or dump.get("message", {}).get("content") or dump.get("text") or "I processed your request."
            dump["id"] = dump.get("id") or f"chatcmpl-{uuid.uuid4().hex[:12]}"
            dump["object"] = "chat.completion"
            dump["created"] = dump.get("created") or int(time.time())
            dump["model"] = dump.get("model") or getattr(self, "model_name", "local-model")
            dump["choices"] = [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": str(content)
                    },
                    "finish_reason": "stop"
                }
            ]
        else:
            if not dump.get("id"):
                dump["id"] = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            if not dump.get("object"):
                dump["object"] = "chat.completion"
            if not dump.get("created"):
                dump["created"] = int(time.time())

        return _ChatCompletion.model_validate(dump)


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
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.device_resolver = device_resolver
        self.tool_registry = tool_registry
        self.devices = devices
        self.settings = settings or {}
        self.context = context or ConversationContext()
        self.event_bridge = event_bridge
        self.privacy_mode = self.settings.get("privacyMode", "local_only")
        self.memory_manager = memory_manager or MemoryManager(
            db_path=self.settings.get("memoryDbPath", "config/memory.db")
        )

        personality_cfg = self.settings.get("personality")
        self.behavior_layer = ConversationBehaviorLayer(
            personality=PersonalityProfile.from_dict(personality_cfg)
        )

        self.model = model or self._resolve_model()
        self.agent = create_pydantic_agent(self.model)
        self._history_messages: List[ModelMessage] = []

    def _resolve_contextual_query(self, query: str) -> str:
        """Enrich short context-dependent queries ('Why?', 'Do it again', 'No, the other one') with conversational anchors."""
        if not self.context.recent_dialogue:
            return query

        q_clean = query.strip().lower().rstrip(".!?")
        last_turn = self.context.recent_dialogue[-1]

        # 1. "Why?" or "How come?"
        if q_clean in ("why", "how come", "why is that", "why not"):
            return f"{query} [Conversational Context: In response to user's previous statement '{last_turn.user_query}', Brown replied '{last_turn.response_text}']"

        # 2. "Do it again" or "Retry"
        if q_clean in ("do it again", "do that again", "repeat that", "run it again", "retry"):
            if self.context.last_action:
                return f"{query} [Conversational Context: Re-execute previous action '{self.context.last_action.tool_name}' on device '{self.context.last_action.target_device}']"

        # 3. "No, the other one"
        if "other one" in q_clean or "not that one" in q_clean:
            return f"{query} [Conversational Context: The user is correcting the choice from previous turn regarding '{last_turn.user_query}']"

        # 4. "Are you sure?"
        if q_clean in ("are you sure", "really"):
            return f"{query} [Conversational Context: User is questioning Brown's previous statement: '{last_turn.response_text}']"

        return query

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
                target_dev_id = self.device_resolver.find_device_for_local_ai()
                target_dev = self.device_resolver.get_device(target_dev_id) if target_dev_id else None
                resolved_url = (target_dev.connection_url if target_dev and target_dev.connection_url else None) or local_ai_url
                base_url = f"{resolved_url.rstrip('/')}/v1"
                client = AsyncOpenAI(
                    base_url=base_url,
                    api_key="ollama",
                    max_retries=0,
                    timeout=httpx.Timeout(connect=2.0, read=25.0, write=5.0, pool=2.0)
                )
                provider = OpenAIProvider(openai_client=client)
                return ResilientLocalOpenAIModel(local_model_name, provider=provider)
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

        enriched_query = self._resolve_contextual_query(query)
        memory_ctx = self.memory_manager.retrieve_context(query)

        deps = BrainDeps(
            device_resolver=self.device_resolver,
            tool_registry=self.tool_registry,
            context=self.context,
            devices=self.devices,
            settings=self.settings,
            privacy_mode=self.privacy_mode,
            event_bridge=self.event_bridge,
            behavior_layer=self.behavior_layer,
            memory_manager=self.memory_manager,
            memory_context=memory_ctx,
        )

        try:
            try:
                run_result = self.agent.run_sync(
                    enriched_query,
                    deps=deps,
                    message_history=self._history_messages,
                )
            except Exception as run_err:
                err_str = str(run_err)
                if any(code in err_str for code in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "Quota exceeded")):
                    logger.warning(f"[BrownBrain] Active model hit quota/rate limit ({run_err}). Attempting fallback cloud models...")
                    all_candidates = ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-flash-lite-latest"]
                    curr_name = getattr(self.model, "model_name", "")
                    fallback_candidates = [m for m in all_candidates if m != curr_name]
                    run_result = None
                    for fb_name in fallback_candidates:
                        try:
                            from pydantic_ai.models.google import GoogleModel
                            fb_model = GoogleModel(fb_name)
                            fb_agent = create_pydantic_agent(fb_model)
                            run_result = fb_agent.run_sync(
                                enriched_query,
                                deps=deps,
                                message_history=self._history_messages,
                            )
                            self.model = fb_model
                            self.agent = fb_agent
                            logger.info(f"[BrownBrain] Successfully transitioned to fallback model: {fb_name}")
                            break
                        except Exception as fb_e:
                            logger.warning(f"[BrownBrain] Fallback candidate {fb_name} failed: {fb_e}")
                    if run_result is None:
                        raise run_err
                else:
                    raise run_err

            # Keep bounded history (last 10 messages)
            self._history_messages.extend(run_result.new_messages())
            if len(self._history_messages) > 10:
                self._history_messages = self._history_messages[-10:]

            raw_output = run_result.output
            spoken_text = self.behavior_layer.filter_response(
                draft=raw_output,
                user_query=query,
                tool_called=deps.last_tool_called,
                tool_success=deps.last_tool_success,
            )
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

            # Asynchronously extract memories without adding latency to speech output
            self.memory_manager.extract_async(query, spoken_text)

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

    def stream_query(
        self,
        query: str,
        cancel_event: Optional[threading.Event] = None
    ) -> Generator[str, None, None]:
        """Stream query output token-by-token or chunk-by-chunk with instant cancellation support."""
        if cancel_event and cancel_event.is_set():
            return

        self.context.prune_expired()
        enriched_query = self._resolve_contextual_query(query)
        memory_ctx = self.memory_manager.retrieve_context(query)

        deps = BrainDeps(
            device_resolver=self.device_resolver,
            tool_registry=self.tool_registry,
            context=self.context,
            devices=self.devices,
            settings=self.settings,
            privacy_mode=self.privacy_mode,
            event_bridge=self.event_bridge,
            behavior_layer=self.behavior_layer,
            memory_manager=self.memory_manager,
            memory_context=memory_ctx,
        )

        try:
            if hasattr(self.agent, "run_stream_sync"):
                with self.agent.run_stream_sync(
                    enriched_query,
                    deps=deps,
                    message_history=self._history_messages,
                ) as stream_result:
                    full_text = []
                    for delta in stream_result.stream_text(delta=True):
                        if cancel_event and cancel_event.is_set():
                            logger.info("[BrownBrain] Stream cancelled mid-generation by turn interruption.")
                            return
                        full_text.append(delta)
                        yield delta

                    # Update history and context if stream wasn't cancelled
                    if not (cancel_event and cancel_event.is_set()):
                        self._history_messages.extend(stream_result.new_messages())
                        if len(self._history_messages) > 10:
                            self._history_messages = self._history_messages[-10:]
                        raw_output = "".join(full_text)
                        spoken_text = self.behavior_layer.filter_response(
                            draft=raw_output,
                            user_query=query,
                            tool_called=deps.last_tool_called,
                            tool_success=deps.last_tool_success,
                        )
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
                        # Extract memories in background
                        self.memory_manager.extract_async(query, spoken_text)
            else:
                resp = self.process_query(query)
                words = resp.text.split(" ")
                for i, word in enumerate(words):
                    if cancel_event and cancel_event.is_set():
                        return
                    prefix = " " if i > 0 else ""
                    yield prefix + word
        except Exception as e:
            logger.warning(f"[BrownBrain] Streaming fallback due to: {e}")
            if cancel_event and cancel_event.is_set():
                return
            resp = self.process_query(query)
            words = resp.text.split(" ")
            for i, word in enumerate(words):
                if cancel_event and cancel_event.is_set():
                    return
                prefix = " " if i > 0 else ""
                yield prefix + word

    def reset_history(self):
        """Clear active dialogue history."""
        self._history_messages.clear()
        self.context = ConversationContext()
