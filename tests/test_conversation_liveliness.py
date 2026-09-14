"""Tests for Brown Conversation Behavior Layer & Liveliness.

Validates the 8 mandatory conversation scenarios:
1. New conversation
2. Multiple follow-up questions
3. Short casual conversation
4. Tool execution
5. Failed tool execution
6. User changing topic
7. Repeated requests
8. Pure conversation without tools
"""

import pytest
from core.conversation_behavior import ConversationBehaviorLayer, PersonalityProfile, InteractionState
from core.ai.brain import BrownBrain
from core.device_resolver import DeviceResolver
from tools.base import ToolRegistry, BaseTool, ToolResult
from agents.local_agent import LocalAgent


class MockOpenAppTool(BaseTool):
    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return "Opens an application"

    def execute(self, app_name: str, device: str = "paperball", **kwargs) -> ToolResult:
        if "fail" in app_name.lower() or device == "unreachable_dev":
            return ToolResult(success=False, message=f"Device {device} offline or application not found.")
        return ToolResult(success=True, message=f"Application '{app_name}' launched on {device}.")


@pytest.fixture
def behavior_layer():
    profile = PersonalityProfile(
        warmth=0.7,
        directness=0.8,
        verbosity=0.3,
        acknowledgement_frequency=0.2,
        response_variation=0.8
    )
    return ConversationBehaviorLayer(profile)


def test_response_quality_canned_opening_removal(behavior_layer):
    """Scenario: Canned assistant openings ('Sure', 'Certainly', 'I can help') are stripped."""
    drafts = [
        ("Sure, it's sitting around 5.1 GB.", "It's sitting around 5.1 GB."),
        ("Certainly! I've opened Safari for you.", "I've opened Safari for you."),
        ("Absolutely. Here is the CPU usage.", "Here is the CPU usage."),
        ("I'd be happy to check that for you. The temperature is 45C.", "The temperature is 45C."),
        ("I can help with that. Spotify is now playing.", "Spotify is now playing."),
        ("Sure thing, done.", "Done."),
    ]
    for raw, expected in drafts:
        filtered = behavior_layer.filter_response(raw, "query")
        assert filtered == expected, f"Failed on '{raw}': got '{filtered}', expected '{expected}'"


def test_response_quality_action_echo_removal(behavior_layer):
    """Scenario: Redundant action restatements before answers are removed."""
    draft = "Checking the RAM for you. It's sitting around 5.1 GB."
    filtered = behavior_layer.filter_response(draft, "What about the RAM?")
    assert filtered == "It's sitting around 5.1 GB."


def test_scenario_1_new_conversation(behavior_layer):
    """Scenario 1: New conversation starts cleanly without canned assistance boilerplate."""
    assert behavior_layer.state.is_new_exchange() is True
    draft = "Sure, Paperball is currently running smoothly with 12% CPU usage."
    filtered = behavior_layer.filter_response(draft, "How is the system doing?")
    assert not filtered.lower().startswith("sure")
    assert "running smoothly" in filtered


def test_scenario_2_multiple_follow_up_questions(behavior_layer):
    """Scenario 2: Follow-up questions are answered directly without repeating acknowledgements."""
    # Turn 1: Is model running?
    t1 = behavior_layer.filter_response("Yeah, it's running.", "Is the local model running?")
    assert t1 == "Yeah, it's running."

    # Turn 2: What about memory? (Should strip repetitive 'Sure' and action echoes)
    t2 = behavior_layer.filter_response("Checking the memory for you. It's using about 5 GB.", "What about memory?")
    assert t2 == "It's using about 5 GB."

    # Turn 3: And the GPU?
    t3 = behavior_layer.filter_response("Around 3 GB.", "And the GPU?")
    assert t3 == "Around 3 GB."

    # Ensure momentum increased
    assert behavior_layer.state.momentum > 0
    assert behavior_layer.state.turn_count == 3


def test_scenario_3_short_casual_conversation(behavior_layer):
    """Scenario 3: Short casual conversation preserves one-word and punchy human answers."""
    casual_answers = [
        "Yeah.", "No.", "Not yet.", "Done.", "It's running.",
        "Give me a second.", "Actually, no.", "That failed."
    ]
    for ans in casual_answers:
        filtered = behavior_layer.filter_response(ans, "casual check")
        assert filtered == ans


def test_scenario_4_tool_execution(behavior_layer):
    """Scenario 4: Tool execution is confirmed cleanly without robotic boilerplate."""
    draft = "I have successfully opened Notes for you."
    # The filter strips "I have successfully"
    filtered = behavior_layer.filter_response(draft, "open Notes", tool_called="open_application", tool_success=True)
    assert not filtered.lower().startswith("i have successfully")
    assert "opened Notes for you." in filtered or "Opened Notes" in filtered


def test_scenario_5_failed_tool_execution(behavior_layer):
    """Scenario 5: Failed tool execution reports problem directly without groveling."""
    draft = "I apologize, but that failed because Error Boy is currently unreachable."
    filtered = behavior_layer.filter_response(draft, "open code on error boy", tool_called="open_application", tool_success=False)
    assert "that failed" in filtered.lower() or "unreachable" in filtered.lower()


def test_scenario_6_user_changing_topic(behavior_layer):
    """Scenario 6: User changing topic transitions cleanly without context collision."""
    behavior_layer.filter_response("Memory is at 4 GB.", "Check memory")
    # User abruptly changes topic
    t2 = behavior_layer.filter_response("I think the simpler architecture is cleaner.", "What do you think of this design?")
    assert "simpler architecture" in t2
    assert behavior_layer.state.last_user_query == "What do you think of this design?"


def test_scenario_7_repeated_requests(behavior_layer):
    """Scenario 7: Repeated requests avoid identical repetitive opening word loops."""
    r1 = behavior_layer.filter_response("Yeah, it's 25% loaded.", "What is the CPU?")
    # Second turn also tries to start with "Yeah,"
    r2 = behavior_layer.filter_response("Yeah, it is still 25% loaded.", "Are you sure?")
    # Repetitive opening 'Yeah,' should be stripped on consecutive turn
    assert not r2.startswith("Yeah,")


def test_scenario_8_pure_conversation_without_tools(behavior_layer):
    """Scenario 8: Pure conversation without tools provides high-quality reasoning."""
    query = "Why do you think local AI is better for this?"
    draft = "Because keeping inference on your local network preserves privacy and has zero subscription costs."
    filtered = behavior_layer.filter_response(draft, query, tool_called=None)
    assert "preserves privacy" in filtered
    assert behavior_layer.state.last_action_name is None


from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, TextPart


def test_brain_end_to_end_behavior():
    """End-to-end integration: BrownBrain applies behavior layer and directives seamlessly."""
    resolver = DeviceResolver()
    registry = ToolRegistry()
    registry.register(MockOpenAppTool())
    devices = {"paperball": LocalAgent()}

    settings = {
        "localAiEnabled": False,
        "cloudAiEnabled": False,
        "personality": {
            "warmth": 0.8,
            "directness": 0.9,
            "verbosity": 0.2,
            "acknowledgement_frequency": 0.1
        }
    }

    async def mock_fn(messages, info):
        # Simulate model returning a draft with robotic opening
        return ModelResponse(parts=[TextPart("Sure, I am online and ready.")])

    model = FunctionModel(mock_fn)
    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=registry,
        devices=devices,
        settings=settings,
        model=model
    )

    # Test that behavior layer is initialized with profile
    assert brain.behavior_layer is not None
    assert brain.behavior_layer.personality.directness == 0.9

    # Test processing pure dialogue through behavior layer
    resp = brain.process_query("Are you there?")
    assert resp.success is True
    assert len(resp.text) > 0
    # Spoken text should have "Sure, " stripped deterministically
    assert not resp.text.lower().startswith("sure")
    assert resp.text == "I am online and ready."
