"""Layered Natural Language Intent & Semantic Understanding Engine for Brown.
Implements:
  Layer 1: Ultra-fast deterministic regex/keyword routing (<0.05ms)
  Layer 2: Semantic intent classification & structured entity extraction
  Layer 3: AI Router delegation for complex reasoning
"""

import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pydantic import BaseModel, Field

from core.device_resolver import DeviceResolver


@dataclass
class RoutedAction:
    action_type: str  # 'tool_call', 'conversation', 'stop', 'unknown'
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    direct_response: Optional[str] = None
    target_device: Optional[str] = None
    confidence: float = 1.0


class SemanticIntent(BaseModel):
    """Validated structured schema for classified user intents."""
    intent: str  # e.g., 'device.status', 'device.running_apps', 'device.open_application', etc.
    device: Optional[str] = None
    application: Optional[str] = None
    url: Optional[str] = None
    confidence: float = 1.0
    raw_text: str = ""
    entities: Dict[str, Any] = Field(default_factory=dict)

    def to_routed_action(self) -> RoutedAction:
        """Convert structured semantic intent into an executable RoutedAction."""
        if self.intent == "stop":
            return RoutedAction(action_type="stop", direct_response="Stopped.", confidence=self.confidence)

        elif self.intent == "device.status":
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_system_status",
                tool_args={"device": self.device or "paperball"},
                target_device=self.device,
                confidence=self.confidence
            )

        elif self.intent == "device.running_apps":
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_running_apps",
                tool_args={"device": self.device or "paperball"},
                target_device=self.device,
                confidence=self.confidence
            )

        elif self.intent == "device.open_application":
            return RoutedAction(
                action_type="tool_call",
                tool_name="open_application",
                tool_args={"app_name": self.application or "", "device": self.device or "paperball"},
                target_device=self.device,
                confidence=self.confidence
            )

        elif self.intent == "device.close_application":
            return RoutedAction(
                action_type="tool_call",
                tool_name="close_application",
                tool_args={"app_name": self.application or "", "device": self.device or "paperball"},
                target_device=self.device,
                confidence=self.confidence
            )

        elif self.intent == "device.open_url":
            return RoutedAction(
                action_type="tool_call",
                tool_name="open_url",
                tool_args={"url": self.url or "", "device": self.device or "paperball"},
                target_device=self.device,
                confidence=self.confidence
            )

        elif self.intent == "device.capabilities":
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_device_capabilities",
                tool_args={"device": self.device or "paperball"},
                target_device=self.device,
                confidence=self.confidence
            )

        elif self.intent == "local_ai.status":
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_local_ai_status",
                tool_args={"device": self.device or "remote_node"},
                target_device=self.device or "remote_node",
                confidence=self.confidence
            )

        elif self.intent == "local_ai.manage":
            return RoutedAction(
                action_type="tool_call",
                tool_name="manage_local_ai",
                tool_args={"action": self.entities.get("action", "warm"), "device": self.device or "remote_node"},
                target_device=self.device or "remote_node",
                confidence=self.confidence
            )

        return RoutedAction(
            action_type="conversation",
            direct_response=self.entities.get("response", "I'm ready for your command."),
            target_device=self.device,
            confidence=self.confidence
        )


class DeterministicIntentRouter:
    """Layer 1: Sub-millisecond deterministic intent matching for unambiguous commands."""

    KNOWN_SITES = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "chatgpt": "https://chat.openai.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
    }

    STOP_WORDS = {"stop", "stop speaking", "cancel", "quiet", "shut up", "hold on", "wait", "actually stop"}

    APP_MAP = {
        "safari": "Safari",
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "chromium": "Chromium",
        "firefox": "Firefox",
        "terminal": "Terminal",
        "iterm": "iTerm",
        "iterm2": "iTerm",
        "alacritty": "Alacritty",
        "kitty": "Kitty",
        "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "code": "Visual Studio Code",
        "calculator": "Calculator",
        "calc": "Calculator",
        "notes": "Notes",
        "finder": "Finder",
        "spotify": "Spotify",
        "slack": "Slack",
        "discord": "Discord",
        "steam": "Steam",
    }

    def __init__(self, device_resolver: Optional[DeviceResolver] = None):
        self.device_resolver = device_resolver or DeviceResolver()
        self.RE_TRAILING_PUNCT = re.compile(r"[?!.,]+$")
        self._recompile_patterns()

    def _recompile_patterns(self):
        dev_pat = self.device_resolver.build_regex_pattern()
        self.RE_STATUS = re.compile(
            rf"(?:how is|what is|how's|what's|check|show|get) (?:the )?(?:status of |health of |load of |temperature of )?({dev_pat}|computer|computers|system|machine|machines)",
            re.IGNORECASE
        )
        self.RE_RUNNING_APPS = re.compile(
            rf"(?:what|which|list)\s+(?:apps|applications|programs)?\s*(?:are\s+)?(?:running|open)\s*(?:on\s+({dev_pat}))?",
            re.IGNORECASE
        )
        self.RE_CAPABILITIES = re.compile(
            rf"(?:what\s+can|capabilities\s+of|features\s+of)\s+({dev_pat})",
            re.IGNORECASE
        )
        self.RE_OPEN_URL_WITH_DEV = re.compile(
            rf"(?:can you |could you |please )?(?:open|launch|go to)\s+(?:website\s+)?(https?://\S+|www\.\S+|\S+\.(?:com|org|io|dev|net|edu|ai)|[a-zA-Z]+)\s+(?:on|in|at)\s+({dev_pat})(?:\s+for me|\s+please)?$",
            re.IGNORECASE
        )
        self.RE_OPEN_URL = re.compile(
            rf"(?:can you |could you |please )?(?:open|launch|go to)\s+(?:website\s+)?(https?://\S+|www\.\S+|\S+\.(?:com|org|io|dev|net|edu|ai)|[a-zA-Z]+)(?:\s+for me|\s+please)?$",
            re.IGNORECASE
        )
        self.RE_OPEN_APP_WITH_DEV = re.compile(
            rf"(?:can you |could you |please )?(?:open|launch|start)\s+(?:up\s+)?([a-zA-Z0-9\s]+?)\s+(?:on|in|at)\s+({dev_pat})(?:\s+for me|\s+please)?$",
            re.IGNORECASE
        )
        self.RE_OPEN_APP = re.compile(
            rf"(?:can you |could you |please )?(?:open|launch|start)\s+(?:up\s+)?([a-zA-Z0-9\s]+?)(?:\s+for me|\s+please)?$",
            re.IGNORECASE
        )
        self.RE_CLOSE_APP_WITH_DEV = re.compile(
            rf"(?:can you |could you |please )?(?:close|quit|exit|kill)\s+([a-zA-Z0-9\s]+?)\s+(?:on|in|at)\s+({dev_pat})(?:\s+for me|\s+please)?$",
            re.IGNORECASE
        )
        self.RE_CLOSE_APP = re.compile(
            rf"(?:can you |could you |please )?(?:close|quit|exit|kill)\s+([a-zA-Z0-9\s]+?)(?:\s+for me|\s+please)?$",
            re.IGNORECASE
        )
        self.RE_LOCAL_AI_STATUS = re.compile(
            rf"(?:(?:is\s+(?:the\s+)?(?:local\s+)?(?:llm|ai|model)\s+running)|(?:what\s+is|check)\s+(?:the\s+)?(?:local\s+)?(?:llm|ai|model)\s+status|is\s+local\s+ai\s+running|check\s+if\s+(?:the\s+)?(?:local\s+)?(?:llm|model)\s+is\s+(?:loaded|running|ready)|local\s+llm\s+status)(?:\s+(?:on|in|at)\s+(?:the\s+)?({dev_pat}))?",
            re.IGNORECASE
        )
        self.RE_WARM_LOCAL_AI = re.compile(
            rf"(?:can\s+you\s+)?(?:run|start|load|warm)\s+(?:it|the\s+local\s+llm|the\s+local\s+ai|the\s+local\s+model|the\s+model)\s+(?:on|in|at)\s+(?:the\s+)?({dev_pat})|(?:can\s+you\s+)?(?:run|start|load|warm)\s+it\s+(?:in|on|at)\s+(?:the\s+)?({dev_pat})|(?:warm|load|start)\s+(?:the\s+)?(?:local\s+)?(?:model|llm)",
            re.IGNORECASE
        )

    def resolve_device(self, target: Optional[str]) -> str:
        return self.device_resolver.resolve(target)

    def match_fast_path(self, text: str) -> Optional[RoutedAction]:
        """Minimal deterministic fast path strictly for emergency/safety events.
        
        All natural language understanding, entity resolution, follow-ups,
        and general commands pass through to the conversational brain.
        """
        clean_text = text.lower().strip()
        clean_text = self.RE_TRAILING_PUNCT.sub("", clean_text).strip()

        # Emergency stop / interruption
        if clean_text in self.STOP_WORDS:
            return RoutedAction(action_type="stop", direct_response="Stopped.")

        return None


    def match_pattern(self, text: str) -> Optional[RoutedAction]:
        """Deterministic pattern matching for explicit legacy command syntax."""
        clean_text = text.lower().strip()
        clean_text = self.RE_TRAILING_PUNCT.sub("", clean_text).strip()

        # Status / Health
        status_match = self.RE_STATUS.search(clean_text)
        if status_match:
            device = self.resolve_device(status_match.group(1))
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_system_status",
                tool_args={"device": device},
                target_device=device
            )

        # Running Apps
        running_apps_match = self.RE_RUNNING_APPS.search(clean_text)
        if running_apps_match:
            device = self.resolve_device(running_apps_match.group(1))
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_running_apps",
                tool_args={"device": device},
                target_device=device
            )

        # Device Capabilities
        capabilities_match = self.RE_CAPABILITIES.search(clean_text)
        if capabilities_match:
            device = self.resolve_device(capabilities_match.group(1))
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_device_capabilities",
                tool_args={"device": device},
                target_device=device
            )

        # Open Website / URL
        open_url_dev = self.RE_OPEN_URL_WITH_DEV.search(clean_text)
        open_url_match = open_url_dev or self.RE_OPEN_URL.search(clean_text)
        if open_url_match:
            target = open_url_match.group(1).lower()
            device = self.resolve_device(open_url_match.group(2) if open_url_dev else None)
            if target in self.KNOWN_SITES:
                return RoutedAction(
                    action_type="tool_call",
                    tool_name="open_url",
                    tool_args={"url": self.KNOWN_SITES[target], "device": device},
                    target_device=device
                )
            elif "." in target:
                return RoutedAction(
                    action_type="tool_call",
                    tool_name="open_url",
                    tool_args={"url": target, "device": device},
                    target_device=device
                )

        # Open Application
        open_app_dev = self.RE_OPEN_APP_WITH_DEV.search(clean_text)
        open_app_match = open_app_dev or self.RE_OPEN_APP.search(clean_text)
        if open_app_match:
            app_raw = open_app_match.group(1).strip().lower()
            device = self.resolve_device(open_app_match.group(2) if open_app_dev else None)

            if app_raw in self.KNOWN_SITES:
                return RoutedAction(
                    action_type="tool_call",
                    tool_name="open_url",
                    tool_args={"url": self.KNOWN_SITES[app_raw], "device": device},
                    target_device=device
                )

            app_name = self.APP_MAP.get(app_raw, app_raw.title())
            return RoutedAction(
                action_type="tool_call",
                tool_name="open_application",
                tool_args={"app_name": app_name, "device": device},
                target_device=device
            )

        # Close Application
        close_app_dev = self.RE_CLOSE_APP_WITH_DEV.search(clean_text)
        close_app_match = close_app_dev or self.RE_CLOSE_APP.search(clean_text)
        if close_app_match:
            app_raw = close_app_match.group(1).strip().lower()
            device = self.resolve_device(close_app_match.group(2) if close_app_dev else None)
            app_name = self.APP_MAP.get(app_raw, app_raw.title())
            return RoutedAction(
                action_type="tool_call",
                tool_name="close_application",
                tool_args={"app_name": app_name, "device": device},
                target_device=device
            )

        # Basic greetings & standard conversation
        if clean_text in ("hey brown", "brown", "are you there", "brown are you there", "hello", "hi"):
            return RoutedAction(
                action_type="conversation",
                direct_response="I'm right here. What can I do for you?"
            )
        if "who are you" in clean_text:
            return RoutedAction(
                action_type="conversation",
                direct_response="I am Brown, your personal computer assistant."
            )

        return None

    def route(self, text: str) -> RoutedAction:
        """Backward-compatible entrypoint: runs fast path, pattern matcher, then semantic layer."""
        fast = self.match_fast_path(text)
        if fast:
            return fast

        matched = self.match_pattern(text)
        if matched:
            return matched

        # Fallback to Semantic Classifier
        classifier = SemanticIntentClassifier(device_resolver=self.device_resolver)
        intent = classifier.classify(text)
        return intent.to_routed_action()


class SemanticIntentClassifier:
    """Layer 2: Robust semantic intent classification & entity extraction.
    Resolves natural, conversational phrasings into validated SemanticIntent schemas.
    """

    def __init__(self, device_resolver: Optional[DeviceResolver] = None):
        self.device_resolver = device_resolver or DeviceResolver()

    def classify(self, text: str) -> SemanticIntent:
        clean = text.lower().strip()
        clean = re.sub(r"[?!.,]+$", "", clean).strip()

        # Extract target device dynamically
        device = self.device_resolver.resolve(clean)

        # 0. Intent: local_ai.status or local_ai.manage
        if any(term in clean for term in (
            "local llm", "local model", "local ai", "llm running", "model running",
            "run it in secondary", "run it on secondary", "run it in the secondary", "run it on the secondary",
            "can you run it", "run it on the other", "run it in the other",
            "warm the model", "load the model", "warm local model"
        )):
            if any(term in clean for term in ("run", "start", "load", "warm")):
                return SemanticIntent(
                    intent="local_ai.manage",
                    device=device or self.device_resolver.default_remote_device,
                    confidence=0.98,
                    raw_text=text,
                    entities={"action": "warm"}
                )
            return SemanticIntent(
                intent="local_ai.status",
                device=device or self.device_resolver.default_remote_device,
                confidence=0.98,
                raw_text=text
            )

        # 1. Intent: device.status
        # All natural phrasing variations requested:
        # "Tell me the status of the machine."
        # "What's the machine doing?"
        # "How's the computer?"
        # "Is everything okay with the computer?"
        # "Can you check the machine?"
        # "What's going on with Error Boy?"
        # "How is my Linux laptop?"
        # "Is Error Boy okay?"
        # "Give me the system status."
        # "How's my laptop?"
        status_patterns = [
            r"status",
            r"how(?:'s|\s+is)\s+(?:the|my)?",
            r"what(?:'s|\s+is)\s+(?:the\s+)?(?:machine|computer|system)\s+doing",
            r"what(?:'s|\s+is)\s+going\s+on",
            r"is\s+.*(?:okay|ok|healthy|running|fine)",
            r"check\s+(?:the|my)?",
            r"system\s+(?:status|health|load)",
            r"load\s+of",
            r"temperature\s+of"
        ]

        # Check if query matches status cues and is asking about health/load/status
        for pat in status_patterns:
            if re.search(pat, clean):
                return SemanticIntent(
                    intent="device.status",
                    device=device,
                    confidence=0.96,
                    raw_text=text
                )

        # 2. Intent: device.running_apps
        # "Can you see what's running over there?"
        # "What apps are open?"
        # "Which applications are currently running?"
        running_patterns = [
            r"(?:what|which|list|show|check|see)\s+(?:apps|applications|programs)?\s*(?:are\s+)?(?:running|open|active)",
            r"(?:apps|applications|programs)\s+(?:are\s+)?(?:running|open|active)",
            r"see\s+what(?:'s|\s+is)\s+running",
            r"running\s+apps",
            r"apps\s+are\s+open"
        ]
        for pat in running_patterns:
            if re.search(pat, clean):
                return SemanticIntent(
                    intent="device.running_apps",
                    device=device,
                    confidence=0.94,
                    raw_text=text
                )

        # 3. Intent: device.open_application
        # "Open Firefox on the other laptop."
        open_app_match = re.search(
            r"(?:can\s+you\s+|could\s+you\s+|please\s+)?(?:open|launch|start)\s+(?:up\s+)?([a-zA-Z0-9\s]+?)(?:\s+(?:on|in|at)\s+.+)?$",
            clean
        )
        if open_app_match and not any(k in clean for k in ("website", "url", ".com", ".org", "http")):
            app_raw = open_app_match.group(1).strip()
            return SemanticIntent(
                intent="device.open_application",
                device=device,
                application=app_raw.title(),
                confidence=0.95,
                raw_text=text
            )

        # 4. Intent: device.capabilities
        if any(p in clean for p in ("what can you do", "what are your capabilities", "what can", "capabilities of")):
            return SemanticIntent(
                intent="device.capabilities",
                device=device,
                confidence=0.95,
                raw_text=text
            )

        # 5. Default Conversation / Clarification
        return SemanticIntent(
            intent="conversation.general",
            device=device,
            confidence=0.7,
            raw_text=text,
            entities={"response": f"I heard you say: {text}. I'm ready for your command."}
        )
