"""Test suite for Identity Memory Fast-Path, Name Extraction Accuracy, and Complexity-Aware Model Routing."""

import os
import tempfile
import pytest

from core.memory.extractor import MemoryExtractor
from core.memory.manager import MemoryManager
from core.intent import DeterministicIntentRouter
from core.device_resolver import DeviceResolver
from tools.base import ToolRegistry
from core.ai.brain import BrownBrain
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, TextPart


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_name_extraction_rejects_gerunds_and_fillers():
    """Verify that verbs ending in -ing and common filler words are NEVER extracted as names."""
    extractor = MemoryExtractor()

    # The exact phrase that previously corrupted memory
    records = extractor.extract("I am building an A assistant which needs to be very lively and it has to understand my problems.")
    assert len(records) == 0, "Must not extract 'building' as a user name"

    # Improving ability
    records = extractor.extract("Actually, I am improving your ability because I want you to be my personal assistant.")
    assert len(records) == 0, "Must not extract 'improving' as a user name"

    # Working / trying / developing
    records = extractor.extract("I am working on this right now.")
    assert len(records) == 0, "Must not extract 'working'"

    records = extractor.extract("I'm trying to fix this bug.")
    assert len(records) == 0, "Must not extract 'trying'"

    # Common adjectives
    records = extractor.extract("I am sorry about that.")
    assert len(records) == 0, "Must not extract 'sorry'"

    records = extractor.extract("I am ready.")
    assert len(records) == 0, "Must not extract 'ready'"


def test_spelled_name_extraction():
    """Verify extraction of explicitly spelled names like 'V-I-K-A-S-H-U-V-I'."""
    extractor = MemoryExtractor()

    # Spelled with dashes
    records = extractor.extract("My name is Vikash.  V-I-K-A-S-H-U-V-I,  Vikash U-V.")
    assert len(records) >= 1
    assert records[0].key == "user_name"
    assert records[0].value == "Vikashuvi"

    # Standard introduction
    records = extractor.extract("My name is Vikash.")
    assert len(records) == 1
    assert records[0].value == "Vikash"

    # Two-part name
    records = extractor.extract("Call me Vikash Uvi.")
    assert len(records) == 1
    assert records[0].value == "Vikash Uvi"


def test_intent_router_identity_fastpath():
    """Verify IntentRouter matches identity queries deterministically (<0.1ms)."""
    router = DeterministicIntentRouter(device_resolver=DeviceResolver())

    for q in ["my real name.", "what is my name", "what's my name", "who am i", "do you know my name", "tell me my name"]:
        action = router.match_pattern(q)
        assert action is not None, f"Failed to match pattern for: {q}"
        assert action.action_type == "memory_lookup"
        assert action.tool_name == "user_name"

    # Editor and project
    action = router.match_pattern("what is my preferred editor?")
    assert action is not None and action.tool_name == "preferred_editor"

    action = router.match_pattern("what project am i working on?")
    assert action is not None and action.tool_name == "current_project"


def test_brain_identity_fastpath_zero_quota(temp_db):
    """Verify BrownBrain resolves identity queries from local memory with zero LLM calls."""
    mgr = MemoryManager(db_path=temp_db)
    mgr.save_fact("user_name", "Vikash")

    resolver = DeviceResolver()
    registry = ToolRegistry()

    # FunctionModel that raises an error if invoked, proving LLM is bypassed
    def unreached_model(messages, info):
        raise AssertionError("LLM should never be invoked for local identity memory lookup!")

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=registry,
        devices={},
        model=FunctionModel(unreached_model),
        memory_manager=mgr,
        settings={"memoryDbPath": temp_db}
    )

    # 1. Non-streaming process_query
    resp = brain.process_query("my real name.")
    assert resp.success is True
    assert "Vikash" in resp.text
    assert resp.latency_ms < 5.0

    resp2 = brain.process_query("what is my name")
    assert resp2.success is True
    assert "Vikash" in resp2.text

    # 2. Streaming query
    stream_chunks = list(brain.stream_query("who am i"))
    full_stream_text = "".join(stream_chunks)
    assert "Vikash" in full_stream_text


def test_complexity_task_classification():
    """Verify tasks are classified into simple vs complex for appropriate model routing."""
    resolver = DeviceResolver()
    registry = ToolRegistry()
    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=registry,
        devices={},
        model=FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("ok")]))
    )

    # Simple queries -> Not complex (save cloud quota)
    assert brain.is_complex_task("How are you?") is False
    assert brain.is_complex_task("Hey, are you there?") is False
    assert brain.is_complex_task("What time is it?") is False
    assert brain.is_complex_task("What's the weather?") is False

    # Complex queries -> Cloud Gemini
    assert brain.is_complex_task("Write a python script to parse logs") is True
    assert brain.is_complex_task("Can you debug this memory leak?") is True
    assert brain.is_complex_task("Implement a binary search algorithm in Rust") is True
    assert brain.is_complex_task("Explain how quantum error correction works in detail") is True
    assert brain.is_complex_task("Analyze the architecture tradeoffs of microservices") is True
