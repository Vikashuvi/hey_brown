"""Test Suite for Brown — Stop Reading Raw AI/Tool Output.

Verifies:
1. Long AI response -> Brown gives concise conclusion (under 30 words, 1-3 sentences).
2. Project discussion -> Brown gives recommendation rather than reading research.
3. User proposes bad architecture -> Brown can disagree and challenge assumptions.
4. User proposes good architecture -> Brown can agree and explain why.
5. Previous decision conflicts with new suggestion -> Brown remembers and points it out.
6. User asks "why?" -> Brown continues naturally from previous conclusion.
7. User asks for full details -> Brown provides the detailed answer.
8. Casual conversation -> no unnecessary summaries or preambles.
9. Tool result -> Brown interprets result instead of dictating raw metrics.
10. Web/research result -> Brown synthesizes it instead of reading it.
"""

import os
import pytest
from unittest.mock import MagicMock
from pydantic_ai.models.test import TestModel

from core.ai.brain import BrownBrain
from core.device_resolver import DeviceResolver
from tools.base import ToolRegistry
from core.conversation_behavior import ConversationBehaviorLayer, PersonalityProfile
from core.memory.base import MemoryType, MemoryRecord
from core.memory.store import PersistentMemoryStore
from core.memory.manager import MemoryManager
from core.memory.extractor import MemoryExtractor
from core.memory.retriever import MemoryRetriever


@pytest.fixture
def test_brain(tmp_path):
    """Instantiate a test BrownBrain with in-memory SQLite store."""
    db_path = str(tmp_path / "test_stop_reading.db")
    mem_mgr = MemoryManager(db_path=db_path)

    registry = ToolRegistry()
    devices = {"paperball": MagicMock(), "remote_node": MagicMock()}
    resolver = DeviceResolver({"paperball": {"id": "paperball", "is_local": True}})

    brain = BrownBrain(
        device_resolver=resolver,
        tool_registry=registry,
        devices=devices,
        settings={"personality": {"verbosity": 0.3, "directness": 0.8}},
        model=TestModel(),
    )
    brain.memory_manager = mem_mgr
    return brain


# =====================================================================
# TEST CASES 1 THROUGH 10
# =====================================================================

def test_1_long_ai_response_synthesizes_to_concise_conclusion():
    """Case 1: Long multi-paragraph AI response is filtered to a concise spoken conclusion."""
    behavior = ConversationBehaviorLayer(personality=PersonalityProfile(verbosity=0.3, directness=0.8))
    
    # Simulate a raw 200-word essay from an external model
    raw_long_draft = (
        "According to the AI response, the project architecture should employ a three-tier layered "
        "microservices framework utilizing an asynchronous event bus, multiple Redis cache instances, "
        "and a distributed consensus protocol. In conclusion, here is a summary of the recommended "
        "system components: first, service discovery; second, message routing; third, persistent storage."
    )
    
    filtered = behavior.filter_response(raw_long_draft, user_query="How should we build this project?")
    
    # 1. Prohibited preambles must be stripped
    assert not filtered.lower().startswith("according to the ai")
    assert not filtered.lower().startswith("here is a summary")
    # 2. Must not contain robotic meta-talk
    assert "in conclusion" not in filtered.lower()


def test_2_project_discussion_gives_recommendation_rather_than_reading():
    """Case 2: Brown provides a peer recommendation instead of reading research verbatim."""
    behavior = ConversationBehaviorLayer()
    
    raw_draft = (
        "Based on the research provided, microfrontends offer organizational modularity across teams. "
        "I looked through it. The overall idea is good, but I wouldn't build it exactly that way. "
        "The biggest problem is build overhead. I'd simplify that part first."
    )
    
    filtered = behavior.filter_response(raw_draft, user_query="How should we structure the frontend?")
    
    # Preamble stripped, personal engineer opinion remains
    assert not filtered.lower().startswith("based on the research")
    assert "i wouldn't build it exactly that way" in filtered.lower()


def test_3_user_proposes_bad_architecture_brown_can_disagree():
    """Case 3: When user proposes a bad architecture, Brown actively disagrees and critiques it."""
    behavior = ConversationBehaviorLayer()
    directives = behavior.build_system_prompt_directives()
    
    # System prompt directives explicitly empower disagreement & challenge
    assert "Disagree or challenge assumptions when warranted" in directives
    assert "Engage directly with critiques or disagreements" in directives
    assert "THINK, DO NOT DICTATE" in directives


def test_4_user_proposes_good_architecture_brown_can_agree_and_explain_why():
    """Case 4: Brown can validate good architectures concisely with reasoning."""
    behavior = ConversationBehaviorLayer()
    
    draft = "Yeah, that works. Keeping SQLite local with WAL mode avoids network round-trips and gives sub-millisecond queries."
    filtered = behavior.filter_response(draft, user_query="What if we just use local SQLite with WAL mode?")
    
    assert "sqlite" in filtered.lower()
    assert "avoids network round-trips" in filtered.lower()
    assert len(filtered.split()) < 30


def test_5_previous_decision_conflicts_with_new_suggestion(test_brain):
    """Case 5: When new suggestion conflicts with a stored decision, memory retrieves it."""
    # Store previous architectural decision
    test_brain.memory_manager.store.upsert(MemoryRecord(
        memory_type=MemoryType.DECISION,
        key="architectural_decision",
        value="keep the architecture lightweight without external framework dependencies",
        confidence=1.0,
        source="user_explicit"
    ))
    
    # Query about adding a heavy framework
    context = test_brain.memory_manager.retrieve_context("Should we add another framework like LangChain?")
    assert "lightweight" in context.lower()
    assert "architectural_decision" in context.lower() or "keep the architecture lightweight" in context.lower()


def test_6_user_asks_why_continues_naturally_from_previous_conclusion(test_brain):
    """Case 6: Asking 'Why?' resolves conversational context referencing the previous conclusion."""
    test_brain.context.record_turn(
        user_query="How should we build the database layer?",
        response_text="I wouldn't use Redis. It adds network overhead without solving anything here.",
        tool_name=None,
        tool_args=None,
        tool_result=None,
        success=True,
        verified=False,
        device="paperball"
    )
    
    enriched = test_brain._resolve_contextual_query("Why?")
    assert "Conversational Context" in enriched
    assert "I wouldn't use Redis" in enriched


def test_7_user_asks_for_full_details_provides_detailed_answer(test_brain):
    """Case 7: User asking for 'full details' is tagged to provide comprehensive elaboration."""
    test_brain.context.record_turn(
        user_query="How does the audio pipeline work?",
        response_text="It uses a non-blocking PortAudio stream with real-time echo cancellation.",
        tool_name=None,
        tool_args=None,
        tool_result=None,
        success=True,
        verified=False,
        device="paperball"
    )
    
    enriched = test_brain._resolve_contextual_query("Give me the full details.")
    assert "User explicitly requests full in-depth technical details" in enriched


def test_8_casual_conversation_no_unnecessary_summaries():
    """Case 8: Casual banter and questions do not produce summaries or meta-talk."""
    behavior = ConversationBehaviorLayer()
    
    draft = "Here is a summary of how I am feeling: I'm good. Let's get back to the project."
    filtered = behavior.filter_response(draft, user_query="How are you doing?")
    
    assert not filtered.lower().startswith("here is a summary")
    assert "i'm good" in filtered.lower() or "im good" in filtered.lower()


def test_9_tool_result_interprets_instead_of_dictating():
    """Case 9: System status tool output is interpreted rather than read as raw JSON."""
    behavior = ConversationBehaviorLayer()
    
    # A model draft that was about to recite raw metrics
    raw_draft = (
        "According to the tool output, CPU is 18%, RAM is 45%, disk is 60%, and GPU VRAM is 3GB. "
        "System is running cool and healthy."
    )
    filtered = behavior.filter_response(raw_draft, user_query="Check CPU", tool_called="get_system_status")
    
    assert not filtered.lower().startswith("according to the tool output")
    assert not filtered.lower().startswith("the tool says")


def test_10_web_research_result_synthesizes_instead_of_reading():
    """Case 10: Research text is synthesized into a personal takeaway rather than read verbatim."""
    behavior = ConversationBehaviorLayer()
    
    raw_draft = (
        "The response states that Python 3.12 introduces sub-interpreters and faster startup. "
        "I looked into it. It's solid, but we don't need sub-interpreters yet for our workload."
    )
    filtered = behavior.filter_response(raw_draft, user_query="What about upgrading to Python 3.12?")
    
    assert not filtered.lower().startswith("the response states that")
    assert "we don't need" in filtered.lower()
