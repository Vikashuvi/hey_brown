import time
from core.state import StateMachine, AssistantState


def test_state_machine_transitions():
    sm = StateMachine(conversation_timeout=1.0)
    assert sm.current_state == AssistantState.SLEEPING

    # Wake word trigger
    assert sm.transition_to(AssistantState.WAKE_DETECTED)
    assert sm.current_state == AssistantState.WAKE_DETECTED

    # Listening
    assert sm.transition_to(AssistantState.LISTENING)
    assert sm.current_state == AssistantState.LISTENING

    # Thinking
    assert sm.transition_to(AssistantState.THINKING)
    assert sm.current_state == AssistantState.THINKING

    # Speaking
    assert sm.transition_to(AssistantState.SPEAKING)
    assert sm.current_state == AssistantState.SPEAKING

    # Active conversation after finished speaking
    assert sm.transition_to(AssistantState.ACTIVE_CONVERSATION)
    assert sm.current_state == AssistantState.ACTIVE_CONVERSATION

    # Duplicate transition returns False
    assert not sm.transition_to(AssistantState.ACTIVE_CONVERSATION)

    # Sleep timeout after inactivity
    time.sleep(1.1)
    triggered = sm.check_timeouts()
    assert triggered
    assert sm.current_state == AssistantState.SLEEPING


def test_state_machine_listeners():
    changes = []

    def on_change(old, new):
        changes.append((old, new))

    sm = StateMachine(on_state_change=on_change)
    sm.transition_to(AssistantState.WAKE_DETECTED)
    sm.transition_to(AssistantState.LISTENING)

    assert len(changes) == 2
    assert changes[0] == (AssistantState.SLEEPING, AssistantState.WAKE_DETECTED)
    assert changes[1] == (AssistantState.WAKE_DETECTED, AssistantState.LISTENING)
