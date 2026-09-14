"""Deterministic Speech Normalizer for Brown TTS.

Translates Markdown, technical shorthand, units, symbols, bullets, and URLs
into clean, natural spoken English for Kokoro TTS without modifying displayed text.
"""

import re
from typing import List


class SpeechNormalizer:
    """Transforms raw LLM output into clean phonetically natural spoken text."""

    # Units and abbreviations conversion map
    UNIT_REPLACEMENTS = [
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*GB\b", re.IGNORECASE), r"\1 gigabytes"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*MB\b", re.IGNORECASE), r"\1 megabytes"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*KB\b", re.IGNORECASE), r"\1 kilobytes"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*TB\b", re.IGNORECASE), r"\1 terabytes"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*ms\b", re.IGNORECASE), r"\1 milliseconds"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*sec\b", re.IGNORECASE), r"\1 seconds"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*s\b", re.IGNORECASE), r"\1 seconds"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*min\b", re.IGNORECASE), r"\1 minutes"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*kHz\b", re.IGNORECASE), r"\1 kilohertz"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*MHz\b", re.IGNORECASE), r"\1 megahertz"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*GHz\b", re.IGNORECASE), r"\1 gigahertz"),
        (re.compile(r"(\d+(?:\.\d+)?)\s*%"), r"\1 percent"),
        (re.compile(r"(\d+(?:\.\d+)?)\s*°?C\b"), r"\1 degrees celsius"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*°?F\b"), r"\1 degrees fahrenheit"),
        (re.compile(r"\b(\d+(?:\.\d+)?)\s*fps\b", re.IGNORECASE), r"\1 frames per second"),
        (re.compile(r"\$(\d+(?:\.\d+)?)\b"), r"\1 dollars"),
    ]

    # Technical abbreviations
    TECHNICAL_ABBREVIATIONS = [
        (re.compile(r"\bCPU\b"), "C P U"),
        (re.compile(r"\bGPU\b"), "G P U"),
        (re.compile(r"\bRAM\b"), "ram"),
        (re.compile(r"\bOS\b"), "O S"),
        (re.compile(r"\bVRAM\b"), "V ram"),
        (re.compile(r"\bTTS\b"), "T T S"),
        (re.compile(r"\bSTT\b"), "S T T"),
        (re.compile(r"\bVAD\b"), "V A D"),
        (re.compile(r"\bLLM\b"), "L L M"),
        (re.compile(r"\bAPI\b"), "A P I"),
        (re.compile(r"\bURL\b"), "U R L"),
        (re.compile(r"\bUI\b"), "U I"),
        (re.compile(r"\bID\b"), "I D"),
        (re.compile(r"\bvs\.\b", re.IGNORECASE), "versus"),
        (re.compile(r"\be\.g\.\b", re.IGNORECASE), "for example"),
        (re.compile(r"\bi\.e\.\b", re.IGNORECASE), "that is"),
        (re.compile(r"\betc\.\b", re.IGNORECASE), "etcetera"),
    ]

    def normalize(self, text: str) -> str:
        """Instance method alias for speech normalization."""
        return self.normalize_for_speech(text)

    @classmethod
    def normalize_for_speech(cls, text: str) -> str:
        """Main entry point: cleans and converts text for speech synthesis."""
        if not text:
            return ""

        s = text.strip()

        # 1. Remove Markdown code blocks (```...```)
        s = re.sub(r"```[\w]*\n?[\s\S]*?```", " Code block omitted. ", s)

        # 2. Convert Markdown links [text](url) -> text
        s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", s)

        # 3. Convert Markdown headers (# Header -> Header.)
        s = re.sub(r"^#{1,6}\s*(.+)$", r"\1.", s, flags=re.MULTILINE)

        # 4. Remove bold, italics, strikethrough, blockquotes
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"__([^_]+)__", r"\1", s)
        s = re.sub(r"_([^_]+)_", r"\1", s)
        s = re.sub(r"~~([^~]+)~~", r"\1", s)
        s = re.sub(r"^\s*>\s*", "", s, flags=re.MULTILINE)

        # 5. Convert bullet points and numbered lists to clean natural pauses
        s = re.sub(r"^\s*[-*+]\s+", "", s, flags=re.MULTILINE)
        s = re.sub(r"^\s*\d+\.\s+", "", s, flags=re.MULTILINE)

        # 6. Normalize inline code `vikashuvi.me` -> vikashuvi dot me
        s = re.sub(r"`([^`]+)`", lambda m: cls._normalize_inline_code(m.group(1)), s)

        # 7. Normalize raw URLs
        s = re.sub(r"https?://(?:www\.)?([^\s]+)", lambda m: cls._normalize_url(m.group(1)), s)

        # 8. Normalize units and technical abbreviations
        for pattern, replacement in cls.UNIT_REPLACEMENTS:
            s = pattern.sub(replacement, s)

        for pattern, replacement in cls.TECHNICAL_ABBREVIATIONS:
            s = pattern.sub(replacement, s)

        # 9. Clean special symbols that sound jarring in TTS
        s = s.replace("&", " and ")
        s = s.replace("+", " plus ")
        s = s.replace("=", " equals ")
        s = s.replace("@", " at ")
        s = s.replace("#", "")
        s = s.replace("`", "")
        s = s.replace("*", "")
        s = s.replace("~", "")
        s = s.replace("|", ", ")
        s = s.replace("\\", " ")

        # 10. Strip emojis and non-alphanumeric unicode symbols
        s = re.sub(r"[^\x00-\x7F]+", " ", s)

        # 11. Normalize linebreaks and excessive punctuation
        s = re.sub(r"[\r\n]+", ". ", s)
        s = re.sub(r"\.{2,}", ". ", s)
        s = re.sub(r"-{2,}", ", ", s)
        s = re.sub(r"\s+", " ", s).strip()

        # Clean punctuation spacing (e.g. " . " -> ". ")
        s = re.sub(r"\s+([.,!?;:])", r"\1", s)

        return s

    @classmethod
    def _normalize_inline_code(cls, code: str) -> str:
        """Convert inline code like 'vikashuvi.me' or 'main.py' to spoken words."""
        clean = code.strip()
        # If it looks like a domain or file: 'foo.bar' -> 'foo dot bar'
        clean = re.sub(r"(\w+)\.(\w+)", r"\1 dot \2", clean)
        clean = clean.replace("_", " ")
        clean = clean.replace("-", " ")
        clean = clean.replace("/", " slash ")
        return clean

    @classmethod
    def _normalize_url(cls, url: str) -> str:
        """Convert URL path to spoken domain: 'vikashuvi.me/about' -> 'vikashuvi dot me slash about'."""
        clean = url.rstrip("/").split("?")[0]  # strip query params
        parts = clean.split("/")
        domain = parts[0]
        domain_spoken = domain.replace(".", " dot ")
        if len(parts) > 1 and parts[1]:
            path_spoken = " slash ".join(p.replace("-", " ").replace("_", " ") for p in parts[1:])
            return f"{domain_spoken} slash {path_spoken}"
        return domain_spoken
