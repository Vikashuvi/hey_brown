import time
import queue
from typing import Optional, List, Tuple, Callable
import numpy as np

from core.orchestrator import BrownOrchestrator
from core.state import AssistantState
from tools.base import ToolRegistry, BaseTool, ToolResult
from voice.audio.base import AudioInput, AudioOutput
from voice.wake.base import WakeWordProvider
from voice.vad.base import VADProvider
from voice.stt.base import STTProvider
from voice.tts.base import TTSProvider


class MockAudioInput(AudioInput):
    def __init__(self, sample_rate: int = 16000):
        self._sample_rate = sample_rate
        self.q = queue.Queue()
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def read_chunk(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        try:
            return self.q.get(timeout=timeout or 0.05)
        except queue.Empty:
            return None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def feed(self, chunk: np.ndarray):
        self.q.put(chunk)


class MockAudioOutput(AudioOutput):
    def __init__(self):
        self._playing = False
        self.interrupted_count = 0
        self.played_texts = []

    def play(self, audio_data: np.ndarray, sample_rate: int, on_complete: Optional[Callable[[], None]] = None) -> bool:
        self._playing = True
        # Simulate short playback
        def _finish():
            time.sleep(0.05)
            if self._playing:
                self._playing = False
                if on_complete:
                    on_complete()
        import threading
        threading.Thread(target=_finish, daemon=True).start()
        return True

    def interrupt(self) -> bool:
        if self._playing:
            self._playing = False
            self.interrupted_count += 1
            return True
        return False

    @property
    def is_playing(self) -> bool:
        return self._playing


class MockWakeProvider(WakeWordProvider):
    def __init__(self):
        self.triggered = False

    def start(self):
        pass

    def stop(self):
        pass

    def reset(self):
        self.triggered = False

    def process_frame(self, frame: np.ndarray) -> Optional[str]:
        if self.triggered:
            self.triggered = False
            return "hey_brown"
        return None


class MockVADProvider(VADProvider):
    def __init__(self):
        self.speech_active = False

    def is_speech(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        return self.speech_active

    def reset(self):
        pass


class MockSTTProvider(STTProvider):
    def __init__(self, transcript: str = "open Safari"):
        self.transcript = transcript

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        return self.transcript


class MockTTSProvider(TTSProvider):
    def synthesize(self, text: str) -> Tuple[np.ndarray, int]:
        # Return 100ms dummy audio
        return np.zeros(1600, dtype=np.float32), 16000


class DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return "dummy open app"

    def execute(self, app_name: str, device: str = "paperball", **kwargs) -> ToolResult:
        return ToolResult(success=True, message=f"Opened {app_name} on {device}.")


def test_orchestrator_wake_to_listening():
    audio_in = MockAudioInput()
    audio_out = MockAudioOutput()
    wake_prov = MockWakeProvider()
    vad_prov = MockVADProvider()
    stt_prov = MockSTTProvider()
    tts_prov = MockTTSProvider()

    registry = ToolRegistry()
    registry.register(DummyTool())

    orch = BrownOrchestrator(
        audio_input=audio_in,
        audio_output=audio_out,
        wake_provider=wake_prov,
        vad_provider=vad_prov,
        stt_provider=stt_prov,
        tts_provider=tts_prov,
        tool_registry=registry,
        conversation_timeout=1.0
    )

    orch.start()
    assert orch.current_state == AssistantState.SLEEPING

    # Trigger wake word
    wake_prov.triggered = True
    audio_in.feed(np.zeros(1280, dtype=np.float32))

    # Allow loop to process wake
    time.sleep(0.2)
    assert orch.current_state in (AssistantState.SPEAKING, AssistantState.LISTENING)

    orch.stop()


def test_orchestrator_barge_in():
    audio_in = MockAudioInput()
    audio_out = MockAudioOutput()
    wake_prov = MockWakeProvider()
    vad_prov = MockVADProvider()
    stt_prov = MockSTTProvider()
    tts_prov = MockTTSProvider()

    registry = ToolRegistry()
    registry.register(DummyTool())

    orch = BrownOrchestrator(
        audio_input=audio_in,
        audio_output=audio_out,
        wake_provider=wake_prov,
        vad_provider=vad_prov,
        stt_provider=stt_prov,
        tts_provider=tts_prov,
        tool_registry=registry,
        conversation_timeout=1.0
    )
    orch.barge_in_grace_period_sec = 0.0
    orch.barge_in_min_frames = 1

    orch.start()

    # Manually transition to SPEAKING
    orch._speak("Long spoken sentence by Brown...", next_state=AssistantState.ACTIVE_CONVERSATION)
    assert orch.current_state == AssistantState.SPEAKING
    assert audio_out.is_playing

    # User starts talking (barge-in!)
    vad_prov.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.5)

    # Let orchestrator loop process barge-in
    time.sleep(0.15)

    # Brown should have aborted playback and transitioned to LISTENING immediately
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING

    orch.stop()
