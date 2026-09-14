"""Base data models and abstractions for Brown's Multi-Tier Memory System.

Supports 4 distinct memory tiers:
- Working Memory: Current active turns and conversational momentum.
- Session Memory: Current session goals, actions, and transient context.
- Personal Memory: Stable user identity, preferences, and personal facts (persistent).
- Episodic Memory: Historical milestones, past session summaries, and key decisions (persistent).
"""

import time
import uuid
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Categorization of stored memories."""
    PERSONAL_FACT = "personal_fact"       # e.g., name, profession, birthday, location
    PREFERENCE = "preference"             # e.g., editor, coding style, communication preference
    PROJECT_CONTEXT = "project_context"   # e.g., project name, repo, tech stack, architecture
    DECISION = "decision"                 # e.g., architectural decision, agreed rule, past choices
    EPISODE = "episode"                   # e.g., session summary, milestone event


class MemoryRecord(BaseModel):
    """A durable, structured piece of conversational memory."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    memory_type: MemoryType
    key: str                              # Canonical search key e.g. "user_name", "preferred_editor"
    value: str                            # Fact or preference text e.g. "Vikashuvi", "VS Code"
    confidence: float = 1.0               # 0.0 to 1.0 (explicit statements = 1.0)
    source: str = "user_explicit"         # "user_explicit", "conversation_inference", "system"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def format_for_prompt(self) -> str:
        """Compact string representation for system prompt injection."""
        clean_key = self.key.replace("_", " ").title()
        return f"{clean_key}: {self.value}"
