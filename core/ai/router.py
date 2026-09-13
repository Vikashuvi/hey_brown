"""Three-Tier AI Router for Brown.
Determines routing across:
  Level 1: Deterministic local tools (<0.1ms)
  Level 2: Local LLM provider (Qwen3.5-2B / Error Boy)
  Level 3: Cloud AI provider (OpenAI / Gemini) with privacy enforcement
Also manages conversation continuity and anaphora/pronoun resolution.
"""

import time
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from core.ai.base import AIProvider, ChatMessage, ToolDefinition, ToolCall, AIResponse
from core.ai.local_provider import LocalAIProvider
from core.ai.cloud_provider import CloudAIProvider
from core.privacy import PrivacyMode, PrivacyFilter
from core.device_resolver import DeviceResolver


class ConversationTurn(BaseModel):
    user_query: str
    response_text: str
    target_device: Optional[str] = None
    tool_name: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)


class ConversationContext:
    """Tracks sliding-window conversation history (last N turns) and active entities."""

    def __init__(self, max_turns: int = 5, session_timeout_sec: float = 60.0):
        self.max_turns = max_turns
        self.session_timeout_sec = session_timeout_sec
        self.history: List[ConversationTurn] = []
        self.last_active_device: Optional[str] = None
        self.last_active_app: Optional[str] = None

    def add_turn(
        self,
        user_query: str,
        response_text: str,
        target_device: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_result: Optional[Dict[str, Any]] = None,
    ):
        self._prune_expired()
        turn = ConversationTurn(
            user_query=user_query,
            response_text=response_text,
            target_device=target_device or self.last_active_device,
            tool_name=tool_name,
            tool_result=tool_result,
        )
        self.history.append(turn)
        if len(self.history) > self.max_turns:
            self.history.pop(0)

        if target_device:
            self.last_active_device = target_device

    def resolve_contextual_device(self, query: str, device_resolver: DeviceResolver) -> str:
        """Resolve pronouns like 'it', 'that computer', 'the machine' to the active entity."""
        clean = query.lower().strip()
        pronoun_cues = [" it ", " it?", " it.", "that machine", "that computer", "the machine", "over there", "on it"]

        # If user explicitly specified an alias, resolve directly
        explicit = device_resolver.resolve(query)
        has_explicit = any(alias in clean for alias in [
            "error boy", "linux", "paperball", "mac", "macbook", "victus", "forge"
        ])

        if has_explicit:
            self.last_active_device = explicit
            return explicit

        # If follow-up pronoun is detected and we have a previous device in memory
        if any(cue in f" {clean} " for cue in pronoun_cues) and self.last_active_device:
            return self.last_active_device

        # Default to resolved device
        return explicit

    def _prune_expired(self):
        now = time.time()
        self.history = [t for t in self.history if now - t.timestamp < self.session_timeout_sec]
        if not self.history:
            self.last_active_device = None
            self.last_active_app = None

    def get_messages_for_llm(self) -> List[ChatMessage]:
        self._prune_expired()
        msgs: List[ChatMessage] = []
        for t in self.history[-3:]:  # Last 3 turns max to keep context tight
            msgs.append(ChatMessage(role="user", content=t.user_query))
            msgs.append(ChatMessage(role="assistant", content=t.response_text))
        return msgs


class RoutingDecision(BaseModel):
    level: int  # 1 (deterministic), 2 (local LLM), 3 (cloud LLM)
    provider_used: str
    action_type: str  # "tool_call", "conversation", "stop"
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    direct_response: Optional[str] = None
    target_device: Optional[str] = None
    confidence: float = 1.0
    fallback_reason: Optional[str] = None
    latency_ms: float = 0.0


class AIRouter:
    """Orchestrates 3-tier intelligence routing with conversational continuity."""

    def __init__(
        self,
        device_resolver: DeviceResolver,
        local_provider: Optional[LocalAIProvider] = None,
        cloud_provider: Optional[CloudAIProvider] = None,
        privacy_mode: str = "local_only",
        deterministic_first: bool = True,
        local_first: bool = True,
        cloud_fallback: bool = False,
    ):
        self.device_resolver = device_resolver
        self.local_provider = local_provider or LocalAIProvider(device_resolver=device_resolver)
        self.cloud_provider = cloud_provider
        self.privacy_mode = privacy_mode
        self.deterministic_first = deterministic_first
        self.local_first = local_first
        self.cloud_fallback = cloud_fallback
        self.context = ConversationContext()

    def route_and_execute_intent(
        self,
        query: str,
        deterministic_match: Optional[RoutingDecision] = None,
        available_tools: Optional[List[ToolDefinition]] = None,
    ) -> RoutingDecision:
        t0 = time.time()
        clean = query.strip()

        # Step 1: Check Level 1 Deterministic Fast Path
        if self.deterministic_first and deterministic_match:
            deterministic_match.latency_ms = round((time.time() - t0) * 1000, 2)
            # Update conversational entity if device was referenced
            if deterministic_match.target_device:
                self.context.last_active_device = deterministic_match.target_device
            return deterministic_match

        # Step 2: Contextual entity resolution (anaphoras: 'it', 'the machine')
        target_device = self.context.resolve_contextual_device(query, self.device_resolver)

        # Build message history with sliding window
        history_msgs = self.context.get_messages_for_llm()
        system_prompt = (
            f"You are Brown, a fast, helpful computer assistant. "
            f"Active local machine: {self.device_resolver.default_local_device}, "
            f"active remote machine: {self.device_resolver.default_remote_device}. "
            f"Current subject device is {target_device}."
        )
        messages = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(history_msgs)
        messages.append(ChatMessage(role="user", content=clean))

        # Step 3: Level 2 Local LLM
        if self.local_first and self.local_provider:
            try:
                local_resp = self.local_provider.chat(messages, tools=available_tools)
                latency = round((time.time() - t0) * 1000, 2)

                if local_resp.tool_calls:
                    tc = local_resp.tool_calls[0]
                    # Ensure device argument is contextualized if not specified
                    args = dict(tc.arguments)
                    if "device" not in args:
                        args["device"] = target_device

                    return RoutingDecision(
                        level=2,
                        provider_used=local_resp.provider,
                        action_type="tool_call",
                        tool_name=tc.name,
                        tool_args=args,
                        target_device=args.get("device", target_device),
                        confidence=0.96,
                        latency_ms=latency
                    )

                if local_resp.content:
                    return RoutingDecision(
                        level=2,
                        provider_used=local_resp.provider,
                        action_type="conversation",
                        direct_response=local_resp.content,
                        target_device=target_device,
                        confidence=0.92,
                        latency_ms=latency
                    )
            except Exception as e:
                # Local failed; record reason and check cloud fallback
                fallback_reason = f"Local provider error: {str(e)}"
            else:
                fallback_reason = "Local model gave empty response"
        else:
            fallback_reason = "Local AI disabled"

        # Step 4: Level 3 Cloud Fallback (Governed strictly by Privacy Policy)
        if self.cloud_fallback and self.cloud_provider:
            if PrivacyFilter.check_cloud_allowed(self.privacy_mode):
                try:
                    cloud_resp = self.cloud_provider.chat(messages, tools=available_tools)
                    latency = round((time.time() - t0) * 1000, 2)

                    if cloud_resp.tool_calls:
                        tc = cloud_resp.tool_calls[0]
                        args = dict(tc.arguments)
                        if "device" not in args:
                            args["device"] = target_device

                        return RoutingDecision(
                            level=3,
                            provider_used=cloud_resp.provider,
                            action_type="tool_call",
                            tool_name=tc.name,
                            tool_args=args,
                            target_device=args.get("device", target_device),
                            confidence=0.98,
                            fallback_reason=fallback_reason,
                            latency_ms=latency
                        )

                    if cloud_resp.content:
                        return RoutingDecision(
                            level=3,
                            provider_used=cloud_resp.provider,
                            action_type="conversation",
                            direct_response=cloud_resp.content,
                            target_device=target_device,
                            confidence=0.95,
                            fallback_reason=fallback_reason,
                            latency_ms=latency
                        )
                except Exception as ce:
                    fallback_reason += f"; Cloud fallback error: {str(ce)}"

        # Step 5: Graceful fallback
        latency = round((time.time() - t0) * 1000, 2)
        return RoutingDecision(
            level=1,
            provider_used="heuristic_fallback",
            action_type="conversation",
            direct_response=f"I heard you say: {query}. How would you like me to help with {self.device_resolver.get_display_name(target_device)}?",
            target_device=target_device,
            confidence=0.6,
            fallback_reason=fallback_reason,
            latency_ms=latency
        )

    async def route_vision(
        self,
        prompt: str,
        images: List[Any],
        target_device: Optional[str] = None,
    ) -> RoutingDecision:
        """Route multimodal image-text requests through privacy boundaries and available providers."""
        t0 = time.time()
        eff_device = target_device or self.context.last_active_device or self.device_resolver.default_local_device
        fallback_reason = None

        # 1. Privacy boundary check
        cloud_permitted = PrivacyFilter.check_cloud_allowed(self.privacy_mode)

        # 2. Local AI Tier (Qwen 2B Multimodal on Error Boy)
        if self.local_first and self.local_provider:
            try:
                content = await self.local_provider.vision(prompt, images)
                latency = round((time.time() - t0) * 1000, 2)
                return RoutingDecision(
                    level=2,
                    provider_used=self.local_provider.name,
                    action_type="conversation",
                    direct_response=content,
                    target_device=eff_device,
                    confidence=0.95,
                    latency_ms=latency
                )
            except Exception as e:
                fallback_reason = f"Local vision error: {str(e)}"

        # 3. Cloud AI Tier (Gemini 2.0 Flash / OpenAI)
        if self.cloud_fallback and self.cloud_provider and cloud_permitted:
            try:
                content = await self.cloud_provider.vision(prompt, images)
                latency = round((time.time() - t0) * 1000, 2)
                return RoutingDecision(
                    level=3,
                    provider_used=self.cloud_provider.name,
                    action_type="conversation",
                    direct_response=content,
                    target_device=eff_device,
                    confidence=0.98,
                    fallback_reason=fallback_reason,
                    latency_ms=latency
                )
            except Exception as e:
                fallback_reason = (fallback_reason or "") + f"; Cloud vision error: {str(e)}"

        # 4. Fallback if vision unavailable or blocked by privacy
        latency = round((time.time() - t0) * 1000, 2)
        if not cloud_permitted and (not self.local_provider or not self.local_provider.is_available):
            msg = "Local vision model is offline on Error Boy, and privacy mode prevents sending screen captures to the cloud."
        else:
            msg = "Visual analysis could not be completed with the current providers."

        return RoutingDecision(
            level=1,
            provider_used="vision_fallback",
            action_type="conversation",
            direct_response=msg,
            target_device=eff_device,
            confidence=0.5,
            fallback_reason=fallback_reason,
            latency_ms=latency
        )

    async def text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Provider-agnostic text query routing."""
        decision = self.route_and_execute_intent(prompt)
        if decision.direct_response:
            return decision.direct_response
        if self.local_provider and self.local_first:
            return await self.local_provider.text(prompt, system_prompt=system_prompt, **kwargs)
        if self.cloud_provider and PrivacyFilter.check_cloud_allowed(self.privacy_mode):
            return await self.cloud_provider.text(prompt, system_prompt=system_prompt, **kwargs)
        return ""

    async def vision(self, prompt: str, images: List[Any], **kwargs) -> str:
        """Provider-agnostic multimodal vision query routing."""
        decision = await self.route_vision(prompt, images)
        return decision.direct_response or ""

