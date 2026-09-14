"""Clause-Level Streaming Buffer for Brown AI Assistant.
Incrementally buffers streaming tokens from LLMs, detecting natural spoken
clause and sentence boundaries to feed TTS in parallel with token generation.
Prevents incomplete/dangling phrases from being synthesized while minimizing time-to-first-audio.
"""

import re
from typing import List, Generator, Optional


class ClauseBuffer:
    """Consumes streaming text tokens and yields complete, natural speech clauses."""

    # Sentence terminators that always complete a clause
    SENTENCE_END_PUNCTUATION = (".", "!", "?")
    
    # Clause terminators that break if sufficient words have accumulated
    CLAUSE_END_PUNCTUATION = (";", ":", ",", "—", " - ")

    # Common abbreviations that should NOT trigger a clause split
    COMMON_ABBREVIATIONS = (
        "mr.", "mrs.", "dr.", "ms.", "prof.", "sr.", "jr.", "vs.", "etc.",
        "e.g.", "i.e.", "u.s.", "u.k.", "a.m.", "p.m.", "fig.", "inc.", "ltd."
    )

    def __init__(self, min_clause_words: int = 4, max_clause_words: int = 25):
        self.min_clause_words = min_clause_words
        self.max_clause_words = max_clause_words
        self._buffer: str = ""

    def append(self, token: str) -> List[str]:
        """Add a token to the buffer and return any ready clauses."""
        self._buffer += token
        return self._extract_clauses()

    def flush(self) -> Optional[str]:
        """Flush and return any remaining text in the buffer at end of generation."""
        remainder = self._buffer.strip()
        self._buffer = ""
        if remainder:
            return remainder
        return None

    def reset(self):
        """Clear buffer without returning text."""
        self._buffer = ""

    def _extract_clauses(self) -> List[str]:
        clauses = []
        while True:
            clause = self._find_next_clause()
            if clause:
                clauses.append(clause)
            else:
                break
        return clauses

    def _find_next_clause(self) -> Optional[str]:
        text = self._buffer.lstrip()
        if not text:
            self._buffer = ""
            return None

        # Search for punctuation boundaries
        for idx, char in enumerate(text):
            # 1. Check sentence terminators
            if char in self.SENTENCE_END_PUNCTUATION:
                candidate = text[:idx + 1]
                words = candidate.split()
                
                # Check for abbreviation like "e.g." or "Dr."
                last_word = words[-1].lower() if words else ""
                if last_word in self.COMMON_ABBREVIATIONS:
                    continue

                # Ensure next character (if present) is a space or end of candidate
                if idx + 1 < len(text) and not text[idx + 1].isspace():
                    continue

                if len(words) >= 1:
                    self._buffer = text[idx + 1:].lstrip()
                    return candidate.strip()

            # 2. Check clause terminators (requires at least min_clause_words)
            elif char in self.CLAUSE_END_PUNCTUATION:
                candidate = text[:idx + 1]
                words = candidate.split()
                if len(words) >= self.min_clause_words:
                    # Don't break on comma inside numbers e.g. "10,000"
                    if char == "," and idx > 0 and idx + 1 < len(text):
                        if text[idx - 1].isdigit() and text[idx + 1].isdigit():
                            continue

                    self._buffer = text[idx + 1:].lstrip()
                    return candidate.strip()

        # 3. If buffer grows excessively long without punctuation, break on word boundary
        words = text.split()
        if len(words) >= self.max_clause_words:
            # Cut at max words
            cut_idx = len(" ".join(words[:self.max_clause_words]))
            clause = text[:cut_idx].strip()
            self._buffer = text[cut_idx:].lstrip()
            return clause

        return None
