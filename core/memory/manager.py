"""Central Memory Manager coordinating Brown's 4-Tier Memory Architecture.

1. Working Memory: Immediate conversational turns, momentum, short-message continuity.
2. Session Memory: Current session actions, devices used, transient goals.
3. Personal Memory: Persistent SQLite storage for user identity and preferences.
4. Episodic Memory: Persistent historical interactions, milestones, past decisions.
"""

import threading
import logging
from typing import Optional, List, Dict, Any

from core.memory.base import MemoryRecord, MemoryType
from core.memory.store import PersistentMemoryStore
from core.memory.extractor import MemoryExtractor
from core.memory.retriever import MemoryRetriever

logger = logging.getLogger("brown.memory.manager")


class MemoryManager:
    """Orchestrates memory extraction, storage, and retrieval across all 4 tiers."""

    def __init__(self, db_path: str = "config/memory.db"):
        self.store = PersistentMemoryStore(db_path=db_path)
        self.extractor = MemoryExtractor()
        self.retriever = MemoryRetriever(self.store)
        self._async_lock = threading.Lock()

    def retrieve_context(self, query: str, limit: int = 4) -> str:
        """Fetch top ranked relevant memories formatted for system prompt injection (<5ms)."""
        records = self.retriever.retrieve(query, limit=limit)
        return self.retriever.format_prompt_block(records)

    def extract_async(self, user_query: str, assistant_response: Optional[str] = None):
        """Asynchronously extract and persist facts without blocking voice response playback."""
        def _worker():
            try:
                records = self.extractor.extract(user_query, assistant_response)
                for rec in records:
                    self.store.upsert(rec)
                    logger.info(f"[MemoryManager] Persisted memory: {rec.key}='{rec.value}' ({rec.memory_type.value})")
            except Exception as e:
                logger.warning(f"[MemoryManager] Async memory extraction failed: {e}")

        threading.Thread(target=_worker, daemon=True, name="MemoryExtractorWorker").start()

    def extract_sync(self, user_query: str, assistant_response: Optional[str] = None) -> List[MemoryRecord]:
        """Synchronously extract and persist facts (primarily for test verification)."""
        records = self.extractor.extract(user_query, assistant_response)
        for rec in records:
            self.store.upsert(rec)
        return records

    def save_fact(
        self,
        key: str,
        value: str,
        memory_type: MemoryType = MemoryType.PERSONAL_FACT,
        source: str = "user_explicit"
    ) -> MemoryRecord:
        """Explicitly store a user fact or preference."""
        rec = MemoryRecord(
            memory_type=memory_type,
            key=key,
            value=value,
            confidence=1.0,
            source=source
        )
        return self.store.upsert(rec)

    def get_user_name(self) -> Optional[str]:
        """Fetch known user name if present."""
        rec = self.store.get("user_name")
        return rec.value if rec else None

    def get_all_personal_facts(self) -> List[MemoryRecord]:
        """List all personal facts."""
        return self.store.list(memory_type=MemoryType.PERSONAL_FACT)

    def clear_all(self):
        """Clear all stored memories."""
        self.store.clear()
