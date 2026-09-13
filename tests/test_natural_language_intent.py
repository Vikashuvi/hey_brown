"""Comprehensive Natural Language Intent & Conversational Continuity Tests.
Verifies all conversational variations from milestone specification:
  - "Tell me the status of the machine."
  - "What's the machine doing?"
  - "How's the computer?"
  - "Is everything okay with the computer?"
  - "Can you check the machine?"
  - "What's going on with Error Boy?"
  - "How is my Linux laptop?"
  - "Is Error Boy okay?"
  - "Give me the system status."
  - "Can you see what's running over there?"
  - "Open Firefox on the other laptop."
  - Follow-up questions with pronoun / anaphora resolution ("it", "the machine").
"""

import pytest
from core.intent import DeterministicIntentRouter, SemanticIntentClassifier, SemanticIntent
from core.device_resolver import DeviceResolver
from core.ai.router import AIRouter, ConversationContext, RoutingDecision
from core.ai.local_provider import LocalAIProvider


def test_natural_language_status_variations():
    resolver = DeviceResolver()
    classifier = SemanticIntentClassifier(device_resolver=resolver)

    test_queries = [
        ("Tell me the status of the machine.", "paperball"),
        ("What's the machine doing?", "paperball"),
        ("How's the computer?", "paperball"),
        ("Is everything okay with the computer?", "paperball"),
        ("Can you check the machine?", "paperball"),
        ("Give me the system status.", "paperball"),
        ("How's my laptop?", "paperball"),
        # Remote Error Boy / Linux variations
        ("What's going on with Error Boy?", "error_boy"),
        ("How is my Linux laptop?", "error_boy"),
        ("Is Error Boy okay?", "error_boy"),
        ("Check the secondary machine", "error_boy"),
        ("How is the other laptop doing?", "error_boy"),
    ]

    for query, expected_device in test_queries:
        intent = classifier.classify(query)
        assert intent.intent == "device.status", f"Failed intent for: {query}"
        assert intent.device == expected_device, f"Failed device {intent.device} != {expected_device} for: {query}"
        action = intent.to_routed_action()
        assert action.action_type == "tool_call"
        assert action.tool_name == "get_system_status"
        assert action.tool_args["device"] == expected_device


def test_natural_language_running_apps():
    resolver = DeviceResolver()
    classifier = SemanticIntentClassifier(device_resolver=resolver)

    queries = [
        ("Can you see what's running over there?", "error_boy"),
        ("What apps are open on Error Boy?", "error_boy"),
        ("Which applications are running?", "paperball"),
        ("List running apps on linux", "error_boy"),
    ]

    for query, expected_device in queries:
        intent = classifier.classify(query)
        assert intent.intent == "device.running_apps", f"Failed intent for: {query}"
        assert intent.device == expected_device, f"Failed device for: {query}"
        action = intent.to_routed_action()
        assert action.action_type == "tool_call"
        assert action.tool_name == "get_running_apps"
        assert action.tool_args["device"] == expected_device


def test_natural_language_open_app():
    resolver = DeviceResolver()
    classifier = SemanticIntentClassifier(device_resolver=resolver)

    intent = classifier.classify("Open Firefox on the other laptop.")
    assert intent.intent == "device.open_application"
    assert intent.device == "error_boy"
    assert intent.application == "Firefox"
    action = intent.to_routed_action()
    assert action.action_type == "tool_call"
    assert action.tool_name == "open_application"
    assert action.tool_args["app_name"] == "Firefox"
    assert action.tool_args["device"] == "error_boy"


def test_conversational_continuity_and_pronouns():
    """Test follow-up turns:
    Turn 1: 'What's the status of Error Boy?' -> Error Boy
    Turn 2: 'How much RAM is it using?' -> 'it' resolves to Error Boy!
    """
    resolver = DeviceResolver()
    ai_router = AIRouter(device_resolver=resolver)

    # Turn 1: Explicit target device
    res1 = ai_router.route_and_execute_intent("What's the status of Error Boy?")
    assert res1.action_type == "tool_call"
    assert res1.tool_name == "get_system_status"
    assert res1.target_device == "error_boy"

    # Simulate tool execution and response
    ai_router.context.add_turn(
        user_query="What's the status of Error Boy?",
        response_text="Error Boy is online. CPU is at 25%, RAM is 68%.",
        target_device="error_boy",
        tool_name="get_system_status",
        tool_result={"online": True, "ram_usage_pct": 68}
    )

    # Turn 2: Follow-up using pronoun 'it'
    res2 = ai_router.route_and_execute_intent("How much RAM is it using?")
    assert res2.target_device == "error_boy", f"Expected error_boy but got {res2.target_device}"
    assert res2.action_type == "tool_call"
    assert res2.tool_name == "get_system_status"


def test_custom_device_alias_renaming():
    """Test user renaming Error Boy to 'Forge' in config without modifying code."""
    custom_config = {
        "paperball": {
            "id": "paperball",
            "display_name": "Paperball",
            "is_local": True,
            "aliases": ["mac", "paperball"]
        },
        "forge": {
            "id": "forge",
            "display_name": "Forge",
            "is_local": False,
            "aliases": ["forge", "linux machine", "secondary laptop"]
        }
    }
    resolver = DeviceResolver(custom_config)
    assert resolver.resolve("Check Forge.") == "forge"
    assert resolver.resolve("How is my Linux machine?") == "forge"
    assert resolver.resolve("Open Firefox on Forge.") == "forge"
