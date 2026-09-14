"""Sub-millisecond Memory Retriever for Brown AI.

Retrieves and ranks relevant Personal, Preference, Project, and Episodic memories
for conversational context injection without polluting the context window.
"""

import time
import re
from typing import List, Dict, Any, Optional

from core.memory.base import MemoryRecord, MemoryType
from core.memory.store import PersistentMemoryStore


class MemoryRetriever:
    """Fast hybrid retriever for memory context injection."""

    # Questions asking directly about user identity or preferences
    IDENTITY_QUESTIONS = {
        "name": ("user_name", "what is my name", "who am i", "do you know my name", "my name"),
        "editor": ("preferred_editor", "what is my editor", "what editor do i use", "my preferred editor", "my favorite editor"),
        "project": ("current_project", "what project am i working on", "what is my project", "this project"),
    }

    def __init__(self, store: PersistentMemoryStore):
        self.store = store

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        """Retrieve top ranked relevant memories for an incoming user query."""
        if not query or not query.strip():
            # Return high-confidence personal facts (like user name)
            return self.store.list(memory_type=MemoryType.PERSONAL_FACT, limit=limit)

        q_lower = query.lower().strip()
        matched_records: List[MemoryRecord] = []
        matched_keys = set()

        # 1. Exact Identity Query Matching (Highest Priority)
        for category, (canonical_key, *triggers) in self.IDENTITY_QUESTIONS.items():
            if any(t in q_lower for t in triggers):
                rec = self.store.get(canonical_key)
                if rec and rec.key not in matched_keys:
                    matched_records.append(rec)
                    matched_keys.add(rec.key)

        # 2. General Personal Facts (Always include user_name if known)
        user_name_rec = self.store.get("user_name")
        if user_name_rec and user_name_rec.key not in matched_keys:
            matched_records.append(user_name_rec)
            matched_keys.add(user_name_rec.key)

        # 3. Keyword / Semantic Search across all memories
        search_results = self.store.search(query, limit=limit)
        for r in search_results:
            if r.key not in matched_keys and len(matched_records) < limit:
                matched_records.append(r)
                matched_keys.add(r.key)

        return matched_records[:limit]

    def format_prompt_block(self, records: List[MemoryRecord]) -> str:
        """Format retrieved memories into a concise, high-priority context block."""
        if not records:
            return ""

        lines = ["[Known User Facts & Persistent Memory]"]
        for r in records:
            lines.append(f"- {r.format_for_prompt()}")
        lines.append("- Use these facts seamlessly as true historical context. Do not announce 'According to my memory'.")

        return "\n".join(lines)
