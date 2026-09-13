"""Authoritative Privacy and Data Protection Layer for Brown.
Enforces local-only boundaries and aggressive redaction of sensitive credentials,
tokens, secrets, and private keys before any external cloud AI dispatch.
"""

from enum import Enum
import re
from typing import Dict, Any, List, Union


class PrivacyMode(str, Enum):
    LOCAL_ONLY = "local_only"
    PRIVATE = "private"
    NORMAL = "normal"


class PrivacyViolationError(Exception):
    """Raised when an operation violates the active PrivacyMode policy."""
    pass


class PrivacyFilter:
    """Aggressively inspects, sanitizes, and redacts sensitive data from prompts and tool inputs/outputs."""

    # Patterns matching sensitive data
    PATTERNS = [
        # OpenAI / Anthropic / Generic API Keys
        (re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,})\b", re.IGNORECASE), "[REDACTED_API_KEY]"),
        (re.compile(r"\b(AIza[0-9A-Za-z-_]{35})\b"), "[REDACTED_GEMINI_KEY]"),
        (re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?"), r"\1=[REDACTED_SECRET]"),
        
        # Bearer tokens & JWTs
        (re.compile(r"(?i)bearer\s+([a-zA-Z0-9_\-\.]{20,})"), "Bearer [REDACTED_TOKEN]"),
        (re.compile(r"\beyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\b"), "[REDACTED_JWT]"),

        # SSH / RSA Private Keys
        (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),

        # Passwords / Credentials in strings
        (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{4,})['\"]?"), r"\1=[REDACTED_PASSWORD]"),

        # Payment card numbers (Luhn-like 13-19 digits)
        (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CARD_NUMBER]"),

        # .env style assignments with secret keywords
        (re.compile(r"(?i)^(AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|PRIVATE_KEY|DATABASE_URL)=.*$", re.MULTILINE), r"\1=[REDACTED_ENV_VAR]"),
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Redact sensitive patterns from arbitrary text."""
        if not text:
            return ""
        sanitized = text
        for pattern, replacement in cls.PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def sanitize_payload(cls, data: Any) -> Any:
        """Recursively redact sensitive strings within JSON-compatible data structures."""
        if isinstance(data, str):
            return cls.sanitize_text(data)
        elif isinstance(data, dict):
            return {k: cls.sanitize_payload(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.sanitize_payload(v) for v in data]
        return data

    @classmethod
    def check_cloud_allowed(cls, privacy_mode: Union[str, PrivacyMode]) -> bool:
        """Check if cloud external calls are allowed under the specified privacy mode."""
        mode = PrivacyMode(privacy_mode) if isinstance(privacy_mode, str) else privacy_mode
        if mode == PrivacyMode.LOCAL_ONLY:
            return False
        return True

    @classmethod
    def prepare_for_cloud(cls, messages: List[Dict[str, Any]], privacy_mode: Union[str, PrivacyMode]) -> List[Dict[str, Any]]:
        """Validate and prepare a chat conversation for cloud AI transmission."""
        mode = PrivacyMode(privacy_mode) if isinstance(privacy_mode, str) else privacy_mode
        if mode == PrivacyMode.LOCAL_ONLY:
            raise PrivacyViolationError("Outbound cloud AI request blocked by PrivacyMode.LOCAL_ONLY policy.")

        # In PRIVATE mode, aggressively sanitize all content
        if mode == PrivacyMode.PRIVATE:
            return [cls.sanitize_payload(m) for m in messages]

        # In NORMAL mode, still redact private keys and raw passwords
        sanitized = []
        for m in messages:
            cleaned = dict(m)
            if "content" in cleaned and isinstance(cleaned["content"], str):
                cleaned["content"] = cls.sanitize_text(cleaned["content"])
            sanitized.append(cleaned)
        return sanitized
