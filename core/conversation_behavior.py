"""Conversation Behavior Layer for Brown.

Implements lightweight, deterministic response quality filtering, interaction state
tracking, momentum calculation, and configurable personality conditioning between
AI generation and TTS. Zero secondary LLM latency overhead (<1ms execution).
"""

import re
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("brown.behavior")


@dataclass
class PersonalityProfile:
    """High-level personality and dialogue style controls."""
    warmth: float = 0.7                     # 0.0 (clinical) to 1.0 (friendly, warm)
    directness: float = 0.8                 # 0.0 (elaborate, polite) to 1.0 (blunt, direct)
    verbosity: float = 0.3                  # 0.0 (ultra-terse) to 1.0 (detailed explanations)
    humor: float = 0.4                      # 0.0 (strictly serious) to 1.0 (witty, dry)
    formality: float = 0.3                  # 0.0 (casual slang/colloquial) to 1.0 (formal)
    curiosity: float = 0.5                  # 0.0 (only answers asked) to 1.0 (proactive follow-ups)
    acknowledgement_frequency: float = 0.2  # Probability of including an acknowledgment like "Got it"
    response_variation: float = 0.8         # Penalty on repeated opening words and structures

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "PersonalityProfile":
        if not data:
            return cls()
        fields = cls.__dataclass_fields__.keys()
        filtered = {k: float(v) for k, v in data.items() if k in fields and isinstance(v, (int, float))}
        return cls(**filtered)


@dataclass
class InteractionState:
    """Short-lived conversational momentum and pattern tracking."""
    session_start_time: float = field(default_factory=time.time)
    last_turn_time: float = field(default_factory=time.time)
    turn_count: int = 0
    momentum: float = 0.0                   # Turn velocity; decays over silence
    last_user_query: Optional[str] = None
    last_brown_response: Optional[str] = None
    last_opening_word: Optional[str] = None
    recent_openings: deque = field(default_factory=lambda: deque(maxlen=6))
    consecutive_acknowledgements: int = 0
    current_topic: Optional[str] = None
    last_action_name: Optional[str] = None
    last_action_success: bool = True

    def record_turn(self, query: str, response: str, action_name: Optional[str] = None, success: bool = True):
        now = time.time()
        elapsed = now - self.last_turn_time
        self.last_turn_time = now
        self.turn_count += 1
        self.last_user_query = query
        self.last_brown_response = response
        self.last_action_name = action_name
        self.last_action_success = success

        # Calculate momentum: fast follow-up within 15 seconds boosts momentum
        if elapsed < 8.0:
            self.momentum = min(3.0, self.momentum + 1.0)
        elif elapsed < 20.0:
            self.momentum = max(0.5, self.momentum * 0.8)
        else:
            self.momentum = 0.0

        # Track opening word
        words = response.strip().split()
        if words:
            first_clean = re.sub(r"[^\w]", "", words[0]).lower()
            self.last_opening_word = first_clean
            self.recent_openings.append(first_clean)

    def is_new_exchange(self, threshold_sec: float = 30.0) -> bool:
        """Determines if the current turn is the start of a new interaction."""
        return self.turn_count == 0 or (time.time() - self.last_turn_time > threshold_sec)


class ConversationBehaviorLayer:
    """Deterministic, lightweight response filter and personality manager."""

    # Canned assistant openings that sound robotic
    CANNED_OPENINGS = [
        re.compile(r"^(sure thing|sure|certainly|absolutely|of course|right away)[,!.]?\s*", re.IGNORECASE),
        re.compile(r"^(i'd be happy to|i would be happy to|i can certainly|i'll be happy to)\s*", re.IGNORECASE),
        re.compile(r"^(i can help with that|i can help you with that|i can do that for you)[,!.]?\s*", re.IGNORECASE),
        re.compile(r"^(as an ai|as an assistant|as your personal assistant)[,]?\s*", re.IGNORECASE),
        re.compile(r"^(i have successfully|successfully|i've successfully)\s*", re.IGNORECASE),
    ]

    # Canned assistant closings
    CANNED_CLOSINGS = [
        re.compile(r"\s*(let me know if you need anything else|is there anything else i can help with|how else can i help you today|feel free to ask if you have questions)[.?!]?$", re.IGNORECASE),
        re.compile(r"\s*(what can i do for you\??|what would you like to do next\??)$", re.IGNORECASE),
    ]

    # Redundant action echo phrases: "Checking the RAM for you...", "Opening Safari for you..."
    ACTION_ECHO_PATTERNS = [
        re.compile(r"^(checking|looking into|fetching|gathering|opening|launching)\s+[a-z0-9\s\-]+(\s+for you)?\.?\s*", re.IGNORECASE),
        re.compile(r"^(i am checking|i'm checking|i am opening|i'm opening|i will open|i'll open)\s+[a-z0-9\s\-]+(\s+for you)?\.?\s*", re.IGNORECASE),
    ]

    def __init__(self, personality: Optional[PersonalityProfile] = None):
        self.personality = personality or PersonalityProfile()
        self.state = InteractionState()

    def update_personality(self, profile: PersonalityProfile):
        self.personality = profile

    def build_system_prompt_directives(self) -> str:
        """Synthesize natural behavioral instructions for LLM system prompt."""
        directives = [
            "\nPersonal AI Partner Behavioral Directives:",
            "- You are Brown: an intelligent, technical, opinionated personal AI partner working side-by-side with the user.",
            "- NEVER begin responses with canned filler like 'Sure', 'Certainly', 'Absolutely', 'I can help with that', 'I'd be happy to', 'Of course', or 'I'm here'. Answer the question or state the result directly.",
            "- You are a genuine peer with a distinct point of view. You are encouraged to:",
            "  * Disagree or challenge assumptions when warranted (e.g., User: 'I think this architecture is perfect.' -> Brown: 'I don't think it is. You're putting too much responsibility into the voice layer.')",
            "  * Engage directly with critiques or disagreements instead of saying 'I understand.' (e.g., User: 'That's a terrible idea.' -> Brown: 'Why? What would you do instead?')",
            "  * Express honest technical opinions and admit uncertainty when you don't know.",
            "  * Joke, banter, or be witty when appropriate, without being overly verbose.",
            "- Short follow-ups require direct answers without ceremony. If the user asks 'What about the RAM?', answer directly: 'It's sitting around 5.1 GB.' Do not say 'Sure, I can check the RAM for you.'",
            "- Embrace short, punchy answers when natural: 'Yeah.', 'No.', 'Not yet.', 'Done.', 'It's running.', 'Give me a second.', 'Actually, no.', 'That failed.'",
            "- Do not restate what the user just said or announce what you are about to do before doing it.",
            "- If an action failed, state the cause plainly and directly without groveling (e.g. 'Error Boy is unreachable, it looks offline.').",
        ]

        # Personality nuance
        if self.personality.directness > 0.6:
            directives.append("- Be extremely concise and direct. Deliver core facts in the first 5 words.")
        if self.personality.verbosity < 0.4:
            directives.append("- Keep spoken answers strictly under 15-20 words unless a detailed technical explanation was explicitly requested.")
        if self.personality.formality < 0.4:
            directives.append("- Use natural contractions ('it's', 'that's', 'didn't', 'couldn't') and colloquial phrasing.")

        if not self.state.is_new_exchange():
            directives.append(f"- Ongoing exchange momentum: active (turn {self.state.turn_count + 1}). Maintain conversational context without re-greeting.")

        return "\n".join(directives)

    def filter_response(self, draft: str, user_query: str, tool_called: Optional[str] = None, tool_success: bool = True) -> str:
        """Clean and polish draft response using deterministic quality policy."""
        if not draft or not draft.strip():
            return "Done." if tool_called else "Yeah."

        text = draft.strip()

        # 1. Strip canned assistant closings ("Let me know if you need anything else", etc.)
        for pattern in self.CANNED_CLOSINGS:
            text = pattern.sub("", text).strip()

        # 2. Check if the response is already a natural short answer
        lower = text.lower().rstrip(".!")
        short_valid = {
            "yeah", "yes", "yep", "no", "nope", "not yet", "done", "it's running",
            "its running", "give me a second", "actually no", "that failed", "try this instead",
            "i'm here", "im here", "online", "all good", "sounds good"
        }
        if lower in short_valid:
            self.state.record_turn(user_query, text, tool_called, tool_success)
            return text

        # 3. Strip canned assistant openings or full introductory filler sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        intro_filler_pattern = re.compile(
            r"^(i'd be happy to|i would be happy to|i'll be happy to|i am happy to|i can certainly|let me check|allow me to)\b",
            re.IGNORECASE
        )
        if len(sentences) >= 2 and intro_filler_pattern.match(sentences[0]):
            cleaned = " ".join(sentences[1:])
        else:
            cleaned = text
            for pattern in self.CANNED_OPENINGS:
                match = pattern.match(cleaned)
                if match:
                    candidate = cleaned[match.end():].strip()
                    if candidate:
                        cleaned = candidate[0].upper() + candidate[1:]
                        break

        # 4. Strip redundant action echoing for follow-ups
        # e.g., "Checking the RAM for you. It's sitting around 5.1 GB." -> "It's sitting around 5.1 GB."
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if len(sentences) >= 2:
            first = sentences[0]
            for pattern in self.ACTION_ECHO_PATTERNS:
                if pattern.match(first):
                    # Drop the echoing first sentence
                    cleaned = " ".join(sentences[1:])
                    break

        # 5. Prevent repetitive consecutive opening words
        # e.g. If last response started with "Yeah," or "I've", avoid repeating it back-to-back
        words = cleaned.split()
        if words and self.state.last_opening_word:
            first_word_clean = re.sub(r"[^\w]", "", words[0]).lower()
            if first_word_clean == self.state.last_opening_word and len(words) > 2:
                # If it's a filler opening like "Yeah, ...", strip it
                if first_word_clean in ("yeah", "yes", "well", "okay", "alright") and words[0].endswith((",", ";")):
                    cleaned = " ".join(words[1:])
                    if cleaned:
                        cleaned = cleaned[0].upper() + cleaned[1:]

        # 6. Fallback sanity check: if all text was stripped, fall back cleanly
        if not cleaned or not cleaned.strip():
            cleaned = text if text else ("Done." if tool_called else "Yeah.")

        # Record this turn in interaction state
        self.state.record_turn(user_query, cleaned, tool_called, tool_success)
        return cleaned

    def get_dynamic_wake_greeting(self) -> str:
        """Returns a natural, minimal wake acknowledgment without robotic canned assistant phrases."""
        now = time.time()
        elapsed = now - self.state.last_turn_time

        if self.state.turn_count > 0 and elapsed < 15.0:
            options = ["Yeah?", "Mm?", "Hey."]
        elif self.state.turn_count > 0 and elapsed < 60.0:
            options = ["Yeah?", "Hey.", "Mm?"]
        else:
            options = ["Hey.", "Yeah?", "Mm?"]

        # Pick one that doesn't match the last opening
        for opt in options:
            first_w = re.sub(r"[^\w]", "", opt.split()[0]).lower()
            if first_w != self.state.last_opening_word:
                return opt

        return options[0]
