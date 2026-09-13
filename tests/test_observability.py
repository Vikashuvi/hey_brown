"""Tests for Observability & Correlation Tracing."""

import time
from core.observability import RequestTrace


def test_request_trace_lifecycle_and_latencies():
    trace = RequestTrace()
    assert trace.request_id.startswith("req_")

    # Record stage timings
    trace.record_stage("wake", 25.4)
    trace.record_stage("stt", 120.5)
    trace.record_stage("intent", 1.2)
    trace.record_stage("local_ai", 450.0)
    trace.record_stage("tool", 15.0)
    trace.record_stage("tts", 85.0)

    time.sleep(0.01)
    finished = trace.finish()

    assert finished["request_id"] == trace.request_id
    assert finished["wake_latency_ms"] == 25.4
    assert finished["stt_latency_ms"] == 120.5
    assert finished["local_ai_latency_ms"] == 450.0
    assert finished["total_latency_ms"] > 0.0


def test_trace_redacts_sensitive_error_messages():
    trace = RequestTrace()
    trace.success = False
    trace.error_message = "Authentication failed with token Bearer eyJhbGciOiJIUzI1Ni.secret and password=mypass"

    safe_dict = trace.to_safe_dict()
    assert "Bearer eyJ" not in safe_dict["error_message"]
    assert "[REDACTED_TOKEN]" in safe_dict["error_message"]
    assert "mypass" not in safe_dict["error_message"]
