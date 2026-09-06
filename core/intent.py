import re
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class RoutedAction:
    action_type: str  # 'tool_call', 'conversation', 'stop', 'unknown'
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    direct_response: Optional[str] = None


class DeterministicIntentRouter:
    """Routes simple deterministic voice commands directly to tools without an LLM.
    Handles commands like:
      - 'open Safari'
      - 'open VS Code on Error Boy'
      - 'open youtube.com'
      - 'open github'
      - 'close Terminal'
      - 'what is the status of Paperball'
      - 'stop' / 'quiet'
    """

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

    def route(self, text: str) -> RoutedAction:
        clean_text = text.lower().strip()
        # Remove trailing punctuation
        clean_text = re.sub(r"[?!.,]+$", "", clean_text).strip()

        # 1. Stop / Interruption
        if clean_text in self.STOP_WORDS:
            return RoutedAction(action_type="stop", direct_response="Stopped.")

        # 2. Status / Health queries
        status_match = re.search(r"(?:how is|what is|how's|what's) (?:the )?(?:status of )?(paperball|error boy)", clean_text)
        if status_match:
            device = "error_boy" if "error" in status_match.group(1) else "paperball"
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_system_status",
                tool_args={"device": device}
            )

        if "status" in clean_text or "health" in clean_text or "running on paperball" in clean_text:
            device = "error_boy" if "error boy" in clean_text else "paperball"
            return RoutedAction(
                action_type="tool_call",
                tool_name="get_system_status",
                tool_args={"device": device}
            )

        # 3. Open Website / URL
        # e.g., "open youtube", "open github.com", "open https://example.com"
        open_url_match = re.search(r"^(?:open|launch|go to)\s+(?:website\s+)?(https?://\S+|www\.\S+|\S+\.(?:com|org|io|dev|net|edu|ai)|[a-zA-Z]+)(?:\s+on\s+(paperball|error boy))?$", clean_text)
        if open_url_match:
            target = open_url_match.group(1).lower()
            device = "error_boy" if (open_url_match.group(2) and "error" in open_url_match.group(2)) else "paperball"

            if target in self.KNOWN_SITES:
                return RoutedAction(
                    action_type="tool_call",
                    tool_name="open_url",
                    tool_args={"url": self.KNOWN_SITES[target], "device": device}
                )
            elif "." in target:
                return RoutedAction(
                    action_type="tool_call",
                    tool_name="open_url",
                    tool_args={"url": target, "device": device}
                )

        # 4. Open Application
        # e.g., "open Safari", "launch Terminal", "open VS Code on Error Boy"
        open_app_match = re.search(r"^(?:open|launch|start)\s+([a-zA-Z0-9\s]+?)(?:\s+on\s+(paperball|error boy))?$", clean_text)
        if open_app_match:
            app_raw = open_app_match.group(1).strip()
            device = "error_boy" if (open_app_match.group(2) and "error" in open_app_match.group(2)) else "paperball"

            # Check if this app name is actually a known website
            if app_raw in self.KNOWN_SITES:
                return RoutedAction(
                    action_type="tool_call",
                    tool_name="open_url",
                    tool_args={"url": self.KNOWN_SITES[app_raw], "device": device}
                )

            # Map common nicknames to official macOS app names
            app_map = {
                "safari": "Safari",
                "chrome": "Google Chrome",
                "google chrome": "Google Chrome",
                "terminal": "Terminal",
                "iterm": "iTerm",
                "iterm2": "iTerm",
                "vs code": "Visual Studio Code",
                "vscode": "Visual Studio Code",
                "code": "Visual Studio Code",
                "calculator": "Calculator",
                "notes": "Notes",
                "finder": "Finder",
                "spotify": "Spotify",
                "slack": "Slack",
                "discord": "Discord",
            }
            app_name = app_map.get(app_raw, app_raw.title())

            return RoutedAction(
                action_type="tool_call",
                tool_name="open_application",
                tool_args={"app_name": app_name, "device": device}
            )

        # 5. Close Application
        close_app_match = re.search(r"^(?:close|quit|exit|kill)\s+([a-zA-Z0-9\s]+?)(?:\s+on\s+(paperball|error boy))?$", clean_text)
        if close_app_match:
            app_raw = close_app_match.group(1).strip()
            device = "error_boy" if (close_app_match.group(2) and "error" in close_app_match.group(2)) else "paperball"
            app_map = {
                "safari": "Safari",
                "chrome": "Google Chrome",
                "google chrome": "Google Chrome",
                "terminal": "Terminal",
                "vs code": "Visual Studio Code",
                "vscode": "Visual Studio Code",
            }
            app_name = app_map.get(app_raw, app_raw.title())
            return RoutedAction(
                action_type="tool_call",
                tool_name="close_application",
                tool_args={"app_name": app_name, "device": device}
            )

        # 6. Basic Conversational turns
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

        if "tell me something interesting" in clean_text:
            return RoutedAction(
                action_type="conversation",
                direct_response="Did you know honey never spoils? Archaeologists have found pots of honey in ancient Egyptian tombs that are over three thousand years old and still perfectly edible."
            )

        # Default fallback: return as conversation query
        return RoutedAction(
            action_type="conversation",
            direct_response=f"I heard you say: {text}. I'm ready for your command."
        )
