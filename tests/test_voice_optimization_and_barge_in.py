import time
import threading
import queue
import numpy as np
import pytest
from typing import Optional, Callable, List

from core.orchestrator import BrownOrchestrator
from core.state import AssistantState
from tools.base import ToolRegistry, BaseTool, ToolResult
from voice.audio.base import AudioInput, AudioOutput
from voice.wake.base import WakeWordProvider
from voice.vad.base import VADProvider
from voice.stt.base import STTProvider
from voice.tts.base import TTSProvider
from voice.tts.speech_normalizer import SpeechNormalizer
from voice.audio.barge_in import AcousticBargeInDetector
from voice.audio.player import InterruptibleAudioPlayer


# =====================================================================
# SPEECH NORMALIZER TEST SUITE
# =====================================================================

def test_speech_normalizer_headers_bold_bullets():
    normalizer = SpeechNormalizer()
    raw = """### System Status
**Running**
- GPU: 3GB"""
    cleaned = normalizer.normalize(raw)
    assert "#" not in cleaned
    assert "*" not in cleaned
    assert "-" not in cleaned
    assert "System" in cleaned and "Status" in cleaned
    assert "Running" in cleaned
    assert "gigabytes" in cleaned


def test_speech_normalizer_inline_code_and_urls():
    normalizer = SpeechNormalizer()
    raw = "Visit `domain.me` or https://errorboy.local/status for info."
    cleaned = normalizer.normalize(raw)
    assert "`" not in cleaned
    assert "https://" not in cleaned
    assert "domain dot me" in cleaned
    assert "dot local" in cleaned
    assert "slash status" in cleaned


def test_speech_normalizer_units_and_symbols():
    normalizer = SpeechNormalizer()
    raw = "RAM is at 50% & latency is 12ms at 45C."
    cleaned = normalizer.normalize(raw)
    assert "%" not in cleaned
    assert "&" not in cleaned
    assert "percent" in cleaned
    assert "and" in cleaned
    assert "milliseconds" in cleaned
    assert "degrees celsius" in cleaned


def test_speech_normalizer_emojis_and_acronyms():
    normalizer = SpeechNormalizer()
    raw = "CPU & GPU status is good! 🚀 Brown VRAM is ready."
    cleaned = normalizer.normalize(raw)
    assert "🚀" not in cleaned
    assert "C P U" in cleaned
    assert "G P U" in cleaned
    assert "V ram" in cleaned


# =====================================================================
# MOCK INFRASTRUCTURE FOR BARGE-IN CASES A THROUGH L
# =====================================================================

class ControllableMockAudioInput(AudioInput):
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

    def clear(self):
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except Exception:
                break


class TrackingMockAudioOutput(AudioOutput):
    def __init__(self):
        self._playing = False
        self.interrupted_count = 0
        self.played_texts = []
        self._clause_queue = queue.Queue()
        self._interrupted = threading.Event()

    def play(self, audio_data: np.ndarray, sample_rate: int, on_complete: Optional[Callable[[], None]] = None) -> bool:
        self._playing = True
        self._interrupted.clear()

        def _finish():
            start_t = time.time()
            while (time.time() - start_t) < 0.4 and not self._interrupted.is_set():
                time.sleep(0.02)
            if self._playing and not self._interrupted.is_set():
                self._playing = False
                if on_complete:
                    on_complete()

        threading.Thread(target=_finish, daemon=True).start()
        return True

    def queue_clause(self, audio_data: np.ndarray, sample_rate: int):
        if not self._interrupted.is_set():
            self._clause_queue.put(audio_data)

    def end_stream(self):
        self._clause_queue.put(None)

    def play_clause_stream(self, on_first_audio: Optional[Callable[[], None]] = None, on_complete: Optional[Callable[[], None]] = None) -> bool:
        self._playing = True
        self._interrupted.clear()

        def _worker():
            if on_first_audio:
                on_first_audio()
            while not self._interrupted.is_set():
                try:
                    item = self._clause_queue.get(timeout=0.2)
                except queue.Empty:
                    break
                if item is None or self._interrupted.is_set():
                    break
                time.sleep(0.05)
            self._playing = False
            if not self._interrupted.is_set() and on_complete:
                on_complete()

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def interrupt(self) -> bool:
        self._interrupted.set()
        while not self._clause_queue.empty():
            try:
                self._clause_queue.get_nowait()
            except Exception:
                break
        was = self._playing
        self._playing = False
        self.interrupted_count += 1
        return was

    @property
    def is_playing(self) -> bool:
        return self._playing


class ControllableMockVAD(VADProvider):
    def __init__(self):
        self.speech_active = False

    def is_speech(self, audio_frame: np.ndarray, sample_rate: int = 16000) -> bool:
        return self.speech_active

    def reset(self):
        pass


class MockWake(WakeWordProvider):
    def __init__(self):
        self.triggered = False

    def start(self): pass
    def stop(self): pass
    def process_frame(self, frame: np.ndarray) -> Optional[str]:
        return "brown" if self.triggered else None
    def reset(self): self.triggered = False


class MockSTT(STTProvider):
    def __init__(self, fixed_text: str = "test query"):
        self.fixed_text = fixed_text

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        return self.fixed_text


class MockTTS(TTSProvider):
    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        return np.ones(1600, dtype=np.float32) * 0.1, 16000


class MockBrainStreaming:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.stream_called = False
        self.stream_interrupted = False

    def stream_query(self, query: str, cancel_event: Optional[threading.Event] = None):
        self.stream_called = True
        try:
            for tok in self.tokens:
                if cancel_event and cancel_event.is_set():
                    self.stream_interrupted = True
                    return
                time.sleep(0.04)
                yield tok
        finally:
            if cancel_event and cancel_event.is_set():
                self.stream_interrupted = True


def build_test_orchestrator(vad_prov, audio_in=None, audio_out=None, brain=None):
    audio_in = audio_in or ControllableMockAudioInput()
    audio_out = audio_out or TrackingMockAudioOutput()
    wake_prov = MockWake()
    stt_prov = MockSTT()
    tts_prov = MockTTS()
    registry = ToolRegistry()

    orch = BrownOrchestrator(
        audio_input=audio_in,
        audio_output=audio_out,
        wake_provider=wake_prov,
        vad_provider=vad_prov,
        stt_provider=stt_prov,
        tts_provider=tts_prov,
        tool_registry=registry,
        brain=brain,
        conversation_timeout=2.0
    )
    orch.barge_in_grace_period_sec = 0.0
    orch.barge_in_min_frames = 2
    return orch, audio_in, audio_out


# =====================================================================
# BARGE-IN SCENARIOS: CASES A THROUGH L
# =====================================================================

def test_case_a_early_interruption_first_clause():
    """Case A: Early interruption during first clause playback."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("First clause of the response.", next_state=AssistantState.ACTIVE_CONVERSATION)
    assert orch.current_state == AssistantState.SPEAKING
    assert audio_out.is_playing

    # User interrupts early (frame 1 & 2)
    vad.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.3)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.3)

    time.sleep(0.2)
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING
    orch.stop()


def test_case_b_mid_sentence_interruption():
    """Case B: Mid-sentence interruption during second clause playback."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("Clause one is finished. Now clause two is being spoken.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.1)
    assert orch.current_state == AssistantState.SPEAKING

    # User breaks in mid-sentence
    vad.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.4)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.4)

    time.sleep(0.2)
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING
    orch.stop()


def test_case_c_late_interruption():
    """Case C: Late interruption near completion."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("Finishing up the last word right now.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.2)

    # Interruption arrives just before completion
    vad.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.35)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.35)

    time.sleep(0.15)
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING
    orch.stop()


def test_case_d_single_word_interruption_wait():
    """Case D: Single-word interruption 'Wait' (<200ms trigger)."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("I am currently processing your long status report.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.05)

    t0 = time.time()
    vad.speech_active = True
    # 2 frames = 160ms
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.5)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.5)

    time.sleep(0.15)
    elapsed_ms = (time.time() - t0) * 1000
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING
    assert elapsed_ms < 350
    orch.stop()


def test_case_e_immediate_redirection_no_do_this():
    """Case E: Multi-word immediate redirection 'No, do this instead'."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("Opening Safari browser for you.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.05)

    vad.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.4)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.4)

    time.sleep(0.15)
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING
    # Verify buffer captures new utterance frames
    assert orch._has_speech_started is True
    orch.stop()


def test_case_f_topic_change_interruption():
    """Case F: Topic change interruption ('Check CPU load instead')."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("Yesterday the weather in San Francisco was sunny and warm.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.05)

    vad.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.45)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.45)

    time.sleep(0.15)
    assert audio_out.interrupted_count >= 1
    assert orch.current_state == AssistantState.LISTENING
    orch.stop()


def test_case_g_rejection_of_transient_noise_clicks():
    """Case G: Non-speech transient noise (single click/mic bump) is rejected."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("Continuing speech without interruption.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.05)

    # VAD is false for noise/click
    vad.speech_active = False
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.9)  # High amplitude click, but not speech

    time.sleep(0.1)
    # Must NOT interrupt playback
    assert audio_out.interrupted_count == 0
    assert orch.current_state == AssistantState.SPEAKING
    orch.stop()


def test_case_h_rejection_of_speaker_bleed_echo():
    """Case H: Low-energy speaker bleed does not trigger self-interruption."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    orch._speak("Brown's own voice echoing softly off the desk.", next_state=AssistantState.ACTIVE_CONVERSATION)
    time.sleep(0.05)

    # Low amplitude bleed below energy floor (e.g. 0.008 RMS)
    vad.speech_active = True
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.008)
    audio_in.feed(np.ones(1280, dtype=np.float32) * 0.008)

    time.sleep(0.1)
    assert audio_out.interrupted_count == 0
    assert orch.current_state == AssistantState.SPEAKING
    orch.stop()


def test_case_i_rapid_successive_interruptions_no_deadlock():
    """Case I: Rapid successive interruptions execute cleanly without hangs or deadlocks."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    for i in range(5):
        orch._turn_cancel_event.clear()
        orch._speak(f"Attempt number {i} to speak.", next_state=AssistantState.ACTIVE_CONVERSATION)
        time.sleep(0.03)
        vad.speech_active = True
        audio_in.feed(np.ones(1280, dtype=np.float32) * 0.4)
        audio_in.feed(np.ones(1280, dtype=np.float32) * 0.4)
        time.sleep(0.08)
        assert orch.current_state == AssistantState.LISTENING

    assert audio_out.interrupted_count >= 5
    orch.stop()


def test_case_j_interruption_during_llm_stream():
    """Case J: Interruption while LLM is generating tokens immediately halts stream."""
    vad = ControllableMockVAD()
    brain = MockBrainStreaming(["First clause here. ", "Second clause here. ", "Third clause here."])
    orch, audio_in, audio_out = build_test_orchestrator(vad, brain=brain)

    # Launch streaming in a thread as orchestrator does
    t = threading.Thread(target=orch._stream_brain_response, args=("Hello", 0.0, 0.0), daemon=True)
    t.start()
    time.sleep(0.06)

    # Interrupt during stream
    orch.interrupt_current_turn("test_llm_interrupt")
    t.join(timeout=1.0)

    assert orch._turn_cancel_event.is_set()
    assert brain.stream_interrupted is True


def test_case_k_interruption_during_tts_synthesis():
    """Case K: Interruption during TTS synthesis aborts playback prior to audio play."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)

    # Pre-cancel turn
    orch._turn_cancel_event.set()
    # Call _speak while turn is cancelled
    orch._speak("This should not play because turn was already cancelled.")

    # Audio player should not have been triggered
    assert audio_out.is_playing is False


def test_case_l_interruption_purges_queued_audio_clauses():
    """Case L: Player queue holding unplayed clauses is immediately purged on interrupt."""
    player = InterruptibleAudioPlayer()
    chunk1 = np.ones(1600, dtype=np.float32) * 0.1
    chunk2 = np.ones(1600, dtype=np.float32) * 0.1

    player.queue_clause(chunk1, 16000)
    player.queue_clause(chunk2, 16000)
    assert not player._clause_queue.empty()

    player.interrupt()
    assert player._clause_queue.empty()


def test_case_m_dynamic_speaker_bleed_rejection_vs_user_speech():
    """Case M: Speaker echo into mic does NOT false-trigger barge-in, but genuine user speech DOES."""
    detector = AcousticBargeInDetector(min_interruption_frames=2)
    detector.set_playback_active(True)

    # 1. Speaker is playing at 0.18 RMS, mic picks up echo at 0.05 RMS (VAD says speech)
    speaker_echo_chunk = np.ones(1280, dtype=np.float32) * 0.05
    for _ in range(6):
        triggered = detector.evaluate_frame(
            speaker_echo_chunk,
            is_vad_speech=True,
            speech_prob=0.8,
            playback_rms=0.18
        )
        assert triggered is False, "Acoustic detector must NOT trigger on speaker bleed"

    # 2. User breaks in with voice over speaker playback (mic jumps to 0.22 RMS)
    user_speech_chunk = np.ones(1280, dtype=np.float32) * 0.22
    # Frame 1: count becomes 1
    t1 = detector.evaluate_frame(user_speech_chunk, is_vad_speech=True, speech_prob=0.85, playback_rms=0.18)
    assert t1 is False
    # Frame 2: count reaches 2, should trigger!
    t2 = detector.evaluate_frame(user_speech_chunk, is_vad_speech=True, speech_prob=0.85, playback_rms=0.18)
    assert t2 is True, "Acoustic detector MUST trigger when user speech exceeds speaker bleed"


def test_case_n_stop_command_silently_halts_without_loopback():
    """Case N: Fast-path stop command halts audio player and does not speak 'Stopped.' loopback."""
    vad = ControllableMockVAD()
    orch, audio_in, audio_out = build_test_orchestrator(vad)
    orch.start()

    # Brown is speaking
    orch._speak("I am giving a long explanation that the user wants to stop right now.")
    assert orch.current_state == AssistantState.SPEAKING
    assert audio_out.is_playing is True

    # User says "hey brown stop" -> STT returns "hey brown stop"
    orch.stt_provider.transcribe = lambda audio, sample_rate=16000: "hey brown stop"
    orch._handle_transcription_and_action(np.zeros(16000, dtype=np.float32))

    # Output player must be halted, and state must be ACTIVE_CONVERSATION
    assert audio_out.is_playing is False
    assert orch.current_state == AssistantState.ACTIVE_CONVERSATION
    orch.stop()
