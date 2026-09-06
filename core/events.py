from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any
import numpy as np


class EventType(str, Enum):
    WAKE_DETECTED = "WAKE_DETECTED"
    SPEECH_STARTED = "SPEECH_STARTED"
    SPEECH_ENDED = "SPEECH_ENDED"
    TRANSCRIPTION_READY = "TRANSCRIPTION_READY"
    INTENT_ROUTED = "INTENT_ROUTED"
    TTS_STARTED = "TTS_STARTED"
    TTS_FINISHED = "TTS_FINISHED"
    BARGE_IN_TRIGGERED = "BARGE_IN_TRIGGERED"
    STATE_CHANGED = "STATE_CHANGED"
    ERROR = "ERROR"


@dataclass
class BrownEvent:
    event_type: EventType
    data: Optional[Any] = None
    message: str = ""
