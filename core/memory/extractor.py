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
    EXPLICIT_NAME_PATTERNS = [
        re.compile(r"\b(?:my name is|call me|the name is)\s+([A-Za-z][a-zA-Z0-9_\-]+(?:\s+[A-Za-z][a-zA-Z0-9_\-]+)?)\b", re.IGNORECASE),
        re.compile(r"\bremember (?:that )?my name is\s+([A-Za-z][a-zA-Z0-9_\-]+(?:\s+[A-Za-z][a-zA-Z0-9_\-]+)?)\b", re.IGNORECASE),
    ]

    # Spelled out names like "V-I-K-A-S-H-U-V-I" or "V - I - K - A - S - H"
    SPELLED_NAME_PATTERN = re.compile(r"\b([A-Za-z](?:[\-\s]+[A-Za-z]){3,})\b")

    # Casual introductions: "i'm ...", "i am ..."
    CASUAL_NAME_PATTERN = re.compile(r"\b(?:i'm|i am)\s+([A-Za-z][a-zA-Z0-9_\-]+)\b", re.IGNORECASE)

    # Words that must NEVER be extracted as names (verbs ending in -ing, adjectives, articles, adverbs)
    DISALLOWED_NAME_WORDS = {
        "here", "back", "done", "fine", "good", "ready", "listening", "speaking",
        "building", "working", "improving", "trying", "doing", "making", "learning",
        "looking", "going", "gonna", "developing", "coding", "testing", "running",
        "writing", "reading", "asking", "using", "saying", "getting", "creating",
        "happy", "sure", "sorry", "tired", "busy", "online", "offline", "new",
        "curious", "excited", "okay", "ok", "a", "an", "the", "just", "not",
        "really", "actually", "currently", "also", "now", "very", "so", "super"
    }

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

    # Explicit Architectural & Technical Decisions
    DECISION_PATTERNS = [
        re.compile(r"\b(?:we|i)\s+decided\s+(?:to\s+|that\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
        re.compile(r"\b(?:we|i)\s+agreed\s+(?:to\s+|that\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
        re.compile(r"\b(?:our|my)\s+decision\s+is\s+(?:to\s+|that\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
        re.compile(r"\b(?:we're|we are)\s+sticking\s+with\s+(.+?)(?:\.|$)", re.IGNORECASE),
    ]

    def extract(self, user_query: str, assistant_response: Optional[str] = None) -> List[MemoryRecord]:
        """Extract any durable memory records from a conversational turn."""
        if not user_query or not user_query.strip():
            return []

        text = user_query.strip()
        records: List[MemoryRecord] = []

        # 1. User Name Extraction
        candidate_name: Optional[str] = None

        # Check for explicit spelled name: e.g. "V-I-K-A-S-H-U-V-I" or "V - I - K - A - S - H"
        spelled_match = self.SPELLED_NAME_PATTERN.search(text)
        if spelled_match:
            spelled_clean = re.sub(r"[\-\s]+", "", spelled_match.group(1)).capitalize()
            if len(spelled_clean) >= 3 and spelled_clean.lower() not in self.DISALLOWED_NAME_WORDS:
                candidate_name = spelled_clean

        # Check explicit patterns: "my name is ...", "call me ..."
        if not candidate_name:
            for pat in self.EXPLICIT_NAME_PATTERNS:
                match = pat.search(text)
                if match:
                    raw_val = match.group(1).strip()
                    words = raw_val.split()
                    if not any(w.lower().endswith("ing") or w.lower() in self.DISALLOWED_NAME_WORDS for w in words):
                        candidate_name = " ".join(w.capitalize() for w in words)
                        break

        # Check casual pattern: "i am ...", "i'm ..." (strictly validated to prevent gerund verbs)
        if not candidate_name:
            match = self.CASUAL_NAME_PATTERN.search(text)
            if match:
                raw_val = match.group(1).strip()
                if (
                    len(raw_val) >= 2
                    and not raw_val.lower().endswith("ing")
                    and raw_val.lower() not in self.DISALLOWED_NAME_WORDS
                ):
                    candidate_name = raw_val.capitalize()

        if candidate_name:
            records.append(MemoryRecord(
                memory_type=MemoryType.PERSONAL_FACT,
                key="user_name",
                value=candidate_name,
                confidence=1.0,
                source="user_explicit"
            ))

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

        # 5. Technical & Architectural Decisions
        for pat in self.DECISION_PATTERNS:
            match = pat.search(text)
            if match:
                val = match.group(1).strip()
                if len(val) >= 4 and not any(r.value.lower() == val.lower() for r in records):
                    records.append(MemoryRecord(
                        memory_type=MemoryType.DECISION,
                        key="architectural_decision",
                        value=val,
                        confidence=0.95,
                        source="user_explicit"
                    ))
                    break

        return records
