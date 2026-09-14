"""Memory Extractor for Brown AI.

Extracts durable user facts, preferences, project context, and decisions from user dialogue.
Operates asynchronously out-of-band to prevent adding latency to the real-time voice pipeline.
"""

import re
import logging
from typing import List, Optional

from core.memory.base import MemoryRecord, MemoryType

logger = logging.getLogger("brown.memory.extractor")


class MemoryExtractor:
    """Extracts structured memories from conversational turns."""

    # Explicit Name Patterns
    NAME_PATTERNS = [
        re.compile(r"\b(?:my name is|call me|i'm|i am)\s+([A-Z][a-zA-Z0-9_\-]+)\b", re.IGNORECASE),
        re.compile(r"\bremember (?:that )?my name is\s+([A-Z][a-zA-Z0-9_\-]+)\b", re.IGNORECASE),
        re.compile(r"\bthe name is\s+([A-Z][a-zA-Z0-9_\-]+)\b", re.IGNORECASE),
    ]

    # Explicit Editor & Tool Preferences
    EDITOR_PATTERNS = [
        re.compile(r"\bmy (?:preferred|favorite|main)?\s*editor is\s+([a-zA-Z0-9_\-\s]+?)(?:\.|$|,)", re.IGNORECASE),
        re.compile(r"\bi (?:prefer|use|love)\s+([a-zA-Z0-9_\-\s]+)\s+as my editor\b", re.IGNORECASE),
    ]

    # Explicit Project Context
    PROJECT_PATTERNS = [
        re.compile(r"\b(?:this|my|our)\s+project is\s+([a-zA-Z0-9_\-\s]+?)(?:\.|$|,)", re.IGNORECASE),
        re.compile(r"\b(?:working on|developing)\s+(?:a project called|project)\s+([a-zA-Z0-9_\-\s]+?)(?:\.|$|,)", re.IGNORECASE),
    ]

    # Explicit "Remember that..." or "Never do..." instructions
    REMEMBER_PATTERNS = [
        re.compile(r"\bremember (?:that )?(.+?)(?:\.|$)", re.IGNORECASE),
        re.compile(r"\bdon't forget (?:that )?(.+?)(?:\.|$)", re.IGNORECASE),
        re.compile(r"\bi always want (?:to )?(.+?)(?:\.|$)", re.IGNORECASE),
        re.compile(r"\bnever (?:do )?(.+?)(?:\.|$)", re.IGNORECASE),
    ]

    def extract(self, user_query: str, assistant_response: Optional[str] = None) -> List[MemoryRecord]:
        """Extract any durable memory records from a conversational turn."""
        if not user_query or not user_query.strip():
            return []

        text = user_query.strip()
        records: List[MemoryRecord] = []

        # 1. User Name Extraction
        for pat in self.NAME_PATTERNS:
            match = pat.search(text)
            if match:
                raw_name = match.group(1).strip()
                # Ignore common words like 'here', 'back', 'done', 'fine', 'good'
                if raw_name.lower() not in ("here", "back", "done", "fine", "good", "ready", "listening", "speaking"):
                    records.append(MemoryRecord(
                        memory_type=MemoryType.PERSONAL_FACT,
                        key="user_name",
                        value=raw_name,
                        confidence=1.0,
                        source="user_explicit"
                    ))
                    break

        # 2. Preferred Editor Extraction
        for pat in self.EDITOR_PATTERNS:
            match = pat.search(text)
            if match:
                val = match.group(1).strip()
                if len(val) >= 2:
                    records.append(MemoryRecord(
                        memory_type=MemoryType.PREFERENCE,
                        key="preferred_editor",
                        value=val,
                        confidence=0.95,
                        source="user_explicit"
                    ))
                    break

        # 3. Project Context Extraction
        for pat in self.PROJECT_PATTERNS:
            match = pat.search(text)
            if match:
                val = match.group(1).strip()
                if len(val) >= 2:
                    records.append(MemoryRecord(
                        memory_type=MemoryType.PROJECT_CONTEXT,
                        key="current_project",
                        value=val,
                        confidence=0.90,
                        source="user_explicit"
                    ))
                    break

        # 4. Explicit Directives ("Remember that...")
        for pat in self.REMEMBER_PATTERNS:
            match = pat.search(text)
            if match:
                val = match.group(1).strip()
                if len(val) >= 4 and not any(r.value.lower() == val.lower() for r in records):
                    # Clean up canonical key
                    key = "user_preference" if "prefer" in val or "want" in val else "instruction"
                    records.append(MemoryRecord(
                        memory_type=MemoryType.PREFERENCE if "prefer" in val or "want" in val else MemoryType.PERSONAL_FACT,
                        key=key,
                        value=val,
                        confidence=0.90,
                        source="user_explicit"
                    ))
                    break

        return records
