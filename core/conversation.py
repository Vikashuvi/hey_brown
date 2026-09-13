"""Bounded Conversation Context & Entity Tracking for Brown.

Maintains recent dialogue, active device/app/task anchors, last action record,
referenced entities, and verified outcomes. Specifically budgeted for compact
context windows on small local models (e.g. Qwen 2B).
"""

import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ActionRecord(BaseModel):
    """Structured record of an executed and verified action."""
    tool_name: str
    target_device: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    success: bool = False
    verified: bool = False
    verified_data: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)


class DialogueTurn(BaseModel):
    """A single user-assistant exchange in memory."""
    user_query: str
    response_text: str
    timestamp: float = Field(default_factory=time.time)
    tool_called: Optional[str] = None
    target_device: Optional[str] = None


class ConversationContext(BaseModel):
    """Bounded, resource-aware conversational context.
    
    Holds active device focus, topic, entity references, and the last executed action.
    Automatically prunes stale focus after configurable TTL (default 90s).
    """
    active_device: str = "paperball"
    active_topic: Optional[str] = None
    active_project: Optional[str] = None
    active_app: Optional[str] = None
    active_task: Optional[str] = None

    # Execution history & verification state
    last_action: Optional[ActionRecord] = None
    last_verified_result: Optional[Dict[str, Any]] = None

    # Entity & pronoun resolution dictionary
    referenced_entities: Dict[str, str] = Field(default_factory=dict)
    unresolved_references: List[str] = Field(default_factory=list)

    # Bounded dialogue turns
    recent_dialogue: List[DialogueTurn] = Field(default_factory=list)
    max_history_turns: int = 4
    ttl_seconds: float = 90.0
    last_interaction_time: float = Field(default_factory=time.time)

    def prune_expired(self, current_time: Optional[float] = None):
        """Drop stale topics/anchors if idle timeout exceeded."""
        now = current_time or time.time()
        if now - self.last_interaction_time > self.ttl_seconds:
            self.active_topic = None
            self.active_app = None
            self.active_task = None
            self.referenced_entities.clear()
            self.unresolved_references.clear()

        # Prune older dialogue turns exceeding max history
        if len(self.recent_dialogue) > self.max_history_turns:
            self.recent_dialogue = self.recent_dialogue[-self.max_history_turns:]

    def record_turn(
        self,
        user_query: str,
        response_text: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        tool_result: Optional[Dict[str, Any]] = None,
        success: bool = True,
        verified: bool = True,
        device: Optional[str] = None,
    ):
        """Record a completed turn and update context anchors."""
        now = time.time()
        self.last_interaction_time = now
        target_dev = device or self.active_device

        if tool_name:
            action = ActionRecord(
                tool_name=tool_name,
                target_device=target_dev,
                arguments=tool_args or {},
                success=success,
                verified=verified,
                verified_data=tool_result,
                timestamp=now,
            )
            self.last_action = action
            if tool_result:
                self.last_verified_result = tool_result

        # Update active device
        if device:
            self.active_device = device

        turn = DialogueTurn(
            user_query=user_query,
            response_text=response_text,
            timestamp=now,
            tool_called=tool_name,
            target_device=target_dev,
        )
        self.recent_dialogue.append(turn)
        self.prune_expired(now)

    def update_entity(self, key: str, value: str):
        """Store a referenced entity (e.g. 'model': 'qwen3-vl:2b', 'app': 'firefox')."""
        self.referenced_entities[key.lower()] = value
        self.last_interaction_time = time.time()

    def set_active_device(self, device: str):
        """Explicitly switch active device focus."""
        clean = device.strip().lower()
        if clean in ("paperball", "mac", "macbook", "host", "local"):
            self.active_device = "paperball"
        elif clean in ("error_boy", "error boy", "linux", "victus", "remote", "remote_node", "secondary"):
            self.active_device = "error_boy"
        else:
            self.active_device = clean
        self.last_interaction_time = time.time()

    def build_prompt_context(self) -> str:
        """Construct a compact context summary string (<80 tokens) for LLM prompts."""
        self.prune_expired()
        lines = [f"Active Device: {self.active_device}"]

        if self.active_topic:
            lines.append(f"Topic: {self.active_topic}")
        if self.active_app:
            lines.append(f"App: {self.active_app}")
        if self.referenced_entities:
            ent_str = ", ".join(f"{k}={v}" for k, v in self.referenced_entities.items())
            lines.append(f"Entities: {ent_str}")
        if self.last_action:
            lines.append(f"Last Action: {self.last_action.tool_name} on {self.last_action.target_device} (success={self.last_action.success})")

        return " | ".join(lines)
