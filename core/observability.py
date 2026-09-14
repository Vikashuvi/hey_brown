"""Observability & Structured Tracing Subsystem for Brown.
Assigns correlation IDs (request_id) to trace the end-to-end lifecycle:
  Wake -> STT -> Intent -> AI -> Tool -> Verification -> TTS
Tracks phase latencies and provider diagnostics with privacy redaction.
"""

import time
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from core.privacy import PrivacyFilter


class RequestTrace(BaseModel):
    """Tracks performance, latency, and telemetry for a single conversational turn."""
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:8]}")
    start_time: float = Field(default_factory=time.time)

    # Latencies in milliseconds
    wake_latency_ms: float = 0.0
    stt_latency_ms: float = 0.0
    intent_latency_ms: float = 0.0
    local_ai_latency_ms: float = 0.0
    cloud_ai_latency_ms: float = 0.0
    tool_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    time_to_first_token_ms: float = 0.0
    time_to_first_clause_ms: float = 0.0
    time_to_first_audio_ms: float = 0.0
    total_latency_ms: float = 0.0

    # High-precision T0..T6 pipeline timestamps
    t0_speech_end: Optional[float] = None
    t1_stt_ready: Optional[float] = None
    t2_agent_decision: Optional[float] = None
    t3_first_token: Optional[float] = None
    t4_first_clause: Optional[float] = None
    t5_tts_start: Optional[float] = None
    t6_audio_playback: Optional[float] = None

    # Decision telemetry
    wake_confidence: float = 1.0
    provider_used: str = "deterministic"
    fallback_reason: Optional[str] = None
    target_device: Optional[str] = None
    tool_name: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

    def mark_t(self, stage: str):
        """Mark a milestone timestamp T0..T6 and calculate progressive latencies."""
        now = time.time()
        stage_key = f"t{stage.lstrip('t')}" if not stage.startswith("t") else stage
        attr_map = {
            "t0": "t0_speech_end",
            "t1": "t1_stt_ready",
            "t2": "t2_agent_decision",
            "t3": "t3_first_token",
            "t4": "t4_first_clause",
            "t5": "t5_tts_start",
            "t6": "t6_audio_playback",
        }
        if stage_key in attr_map:
            setattr(self, attr_map[stage_key], now)
            base = self.t0_speech_end or self.start_time
            if stage_key == "t3":
                self.time_to_first_token_ms = round((now - base) * 1000.0, 2)
            elif stage_key == "t4":
                self.time_to_first_clause_ms = round((now - base) * 1000.0, 2)
            elif stage_key == "t6":
                self.time_to_first_audio_ms = round((now - base) * 1000.0, 2)

    def record_stage(self, stage: str, latency_ms: float):
        attr = f"{stage}_latency_ms"
        if hasattr(self, attr):
            setattr(self, attr, round(latency_ms, 2))

    def finish(self) -> Dict[str, Any]:
        self.total_latency_ms = round((time.time() - self.start_time) * 1000, 2)
        if self.t6_audio_playback and (self.t0_speech_end or self.start_time):
            base = self.t0_speech_end or self.start_time
            self.time_to_first_audio_ms = round((self.t6_audio_playback - base) * 1000.0, 2)
        return self.to_safe_dict()

    def to_safe_dict(self) -> Dict[str, Any]:
        """Convert trace to privacy-safe dictionary with masked secrets."""
        raw = self.model_dump()
        return PrivacyFilter.sanitize_payload(raw)

    def log_summary(self):
        """Log concise structured trace for developer observability."""
        summary = (
            f"[Observability] {self.request_id} | "
            f"Total: {self.total_latency_ms:.1f}ms | "
            f"Provider: {self.provider_used} | "
            f"Device: {self.target_device or 'local'} | "
            f"Tool: {self.tool_name or 'none'} | "
            f"STT: {self.stt_latency_ms:.1f}ms | "
            f"AI: {self.local_ai_latency_ms or self.cloud_ai_latency_ms:.1f}ms | "
            f"TTS: {self.tts_latency_ms:.1f}ms"
        )
        if self.fallback_reason:
            summary += f" | Fallback: {self.fallback_reason}"
        if not self.success:
            summary += f" | Error: {self.error_message}"
        print(summary)
