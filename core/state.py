from enum import Enum
import time
from typing import Optional, Callable, Dict, List


class AssistantState(str, Enum):
    SLEEPING = "SLEEPING"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ACTIVE_CONVERSATION = "ACTIVE_CONVERSATION"


class StateMachine:
    """Manages conversational and execution states for Brown.
    Transitions:
      SLEEPING -> WAKE_DETECTED (on wake word)
      WAKE_DETECTED -> LISTENING (ready to record user query)
      LISTENING -> THINKING (on silence/end-of-speech detected by VAD)
      THINKING -> SPEAKING (when response ready to play)
      SPEAKING -> LISTENING (on barge-in/interruption)
      SPEAKING -> ACTIVE_CONVERSATION (when finished speaking without interruption)
      ACTIVE_CONVERSATION -> LISTENING (user started speaking again within follow-up window)
      ACTIVE_CONVERSATION -> SLEEPING (follow-up timeout expired)
      LISTENING -> SLEEPING (silence timeout in follow-up)
    """

    def __init__(self, conversation_timeout: float = 8.0, on_state_change: Optional[Callable[[AssistantState, AssistantState], None]] = None):
        self._state = AssistantState.SLEEPING
        self.conversation_timeout = conversation_timeout
        self.last_state_change_time = time.time()
        self.last_interaction_time = time.time()
        self.on_state_change = on_state_change
        self._listeners: List[Callable[[AssistantState, AssistantState], None]] = []
        if on_state_change:
            self._listeners.append(on_state_change)

    @property
    def current_state(self) -> AssistantState:
        return self._state

    def add_listener(self, listener: Callable[[AssistantState, AssistantState], None]):
        self._listeners.append(listener)

    def transition_to(self, new_state: AssistantState, reason: str = "") -> bool:
        if self._state == new_state:
            return False

        old_state = self._state
        self._state = new_state
        self.last_state_change_time = time.time()
        if new_state in (AssistantState.LISTENING, AssistantState.SPEAKING, AssistantState.THINKING):
            self.last_interaction_time = time.time()

        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                print(f"[StateMachine] Listener error during {old_state} -> {new_state}: {e}")

        return True

    def check_timeouts(self) -> bool:
        """Call periodically from event loop. Returns True if a timeout triggered a state transition."""
        now = time.time()
        if self._state == AssistantState.ACTIVE_CONVERSATION:
            if now - self.last_state_change_time > self.conversation_timeout:
                self.transition_to(AssistantState.SLEEPING, reason="conversation_timeout")
                return True
        return False
