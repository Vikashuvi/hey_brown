"""Unit tests for Phase F (Clause-Level Streaming) & Phase G (Latency Instrumentation)."""

import time
import pytest
from voice.audio.clause_buffer import ClauseBuffer
from core.observability import RequestTrace


def test_clause_buffer_sentence_boundaries():
    buffer = ClauseBuffer(min_clause_words=3)
    
    tokens = ["Ollama ", "is ", "running ", "on ", "the ", "remote ", "node. ", "All ", "models ", "are ", "ready!"]
    clauses = []
    for tok in tokens:
        ready = buffer.append(tok)
        clauses.extend(ready)
    
    assert len(clauses) == 2
    assert clauses[0] == "Ollama is running on the remote node."
    assert clauses[1] == "All models are ready!"
    assert buffer.flush() is None


def test_clause_buffer_comma_clause_boundary():
    buffer = ClauseBuffer(min_clause_words=4)
    
    tokens = ["When ", "you ", "are ", "ready, ", "I ", "will ", "open ", "the ", "application."]
    clauses = []
    for tok in tokens:
        ready = buffer.append(tok)
        clauses.extend(ready)

    assert len(clauses) == 2
    assert clauses[0] == "When you are ready,"
    assert clauses[1] == "I will open the application."


def test_clause_buffer_abbreviation_preservation():
    buffer = ClauseBuffer(min_clause_words=3)
    
    # "Dr." should not cause a premature clause cut
    tokens = ["Hello ", "Dr. ", "Watson, ", "the ", "test ", "has ", "passed."]
    clauses = []
    for tok in tokens:
        ready = buffer.append(tok)
        clauses.extend(ready)

    assert len(clauses) >= 1
    # Check that "Dr." was kept intact inside the first clause
    assert "Dr." in clauses[0]


def test_clause_buffer_flush_remainder():
    buffer = ClauseBuffer(min_clause_words=4)
    tokens = ["This ", "is ", "a ", "partial ", "sentence ", "without ", "punctuation"]
    clauses = []
    for tok in tokens:
        clauses.extend(buffer.append(tok))
    
    assert len(clauses) == 0  # No punctuation yet
    remainder = buffer.flush()
    assert remainder == "This is a partial sentence without punctuation"


def test_request_trace_t0_to_t6_telemetry():
    trace = RequestTrace()
    
    # Simulate turn pipeline milestones
    trace.mark_t("t0")  # End of speech
    time.sleep(0.01)
    trace.mark_t("t1")  # STT ready
    time.sleep(0.01)
    trace.mark_t("t2")  # Agent decision
    time.sleep(0.01)
    trace.mark_t("t3")  # First token
    time.sleep(0.01)
    trace.mark_t("t4")  # First complete clause
    time.sleep(0.01)
    trace.mark_t("t5")  # TTS start
    time.sleep(0.01)
    trace.mark_t("t6")  # First audio playback

    summary = trace.finish()
    
    assert trace.t0_speech_end is not None
    assert trace.t1_stt_ready is not None
    assert trace.t6_audio_playback is not None
    assert trace.time_to_first_token_ms > 0.0
    assert trace.time_to_first_clause_ms > 0.0
    assert trace.time_to_first_audio_ms > 0.0
    assert summary["time_to_first_audio_ms"] > 0.0
