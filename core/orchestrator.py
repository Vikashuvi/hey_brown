import time
import threading
from typing import Optional, List
import numpy as np

from core.state import StateMachine, AssistantState
from core.intent import DeterministicIntentRouter, RoutedAction
from core.events import BrownEvent, EventType
from tools.base import ToolRegistry
from voice.audio.base import AudioInput, AudioOutput
from voice.wake.base import WakeWordProvider
from voice.vad.base import VADProvider
from voice.stt.base import STTProvider
from voice.tts.base import TTSProvider


class BrownOrchestrator:
    """Core orchestrator for Brown.
    Coordinates audio I/O, wake word, VAD, STT, deterministic routing,
    typed tools, TTS playback, and instant barge-in interruption.
    """

    def __init__(
        self,
        audio_input: AudioInput,
        audio_output: AudioOutput,
        wake_provider: WakeWordProvider,
        vad_provider: VADProvider,
        stt_provider: STTProvider,
        tts_provider: TTSProvider,
        tool_registry: ToolRegistry,
        conversation_timeout: float = 8.0,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 700,
        greeting: str = "Yeah, I'm here. What can I do for you?"
    ):
        self.audio_input = audio_input
        self.audio_output = audio_output
        self.wake_provider = wake_provider
        self.vad_provider = vad_provider
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.tool_registry = tool_registry
        self.greeting = greeting

        self.barge_in_enabled = True
        self.barge_in_grace_period_sec = 1.2  # Ignore mic for 1.2s of playback to prevent speaker echo
        self.barge_in_min_frames = 3          # Require sustained speech to interrupt

        self.intent_router = DeterministicIntentRouter()
        self.state_machine = StateMachine(
            conversation_timeout=conversation_timeout,
            on_state_change=self._on_state_change
        )

        self.min_speech_frames = int((min_speech_duration_ms / 1000.0) / 0.08)  # 80ms per chunk
        self.min_silence_frames = int((min_silence_duration_ms / 1000.0) / 0.08)

        self._running = False
        self._loop_thread: Optional[threading.Thread] = None

        # Buffers & Timing
        self._speech_buffer: List[np.ndarray] = []
        self._has_speech_started = False
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._barge_in_frame_count = 0
        self._speaking_start_time = 0.0
        self._ignore_mic_until = 0.0

    @property
    def current_state(self) -> AssistantState:
        return self.state_machine.current_state

    def _on_state_change(self, old_state: AssistantState, new_state: AssistantState):
        print(f"[Brown] State: {old_state.value} -> {new_state.value}")
        if new_state == AssistantState.SLEEPING:
            self._speech_buffer.clear()
            self._has_speech_started = False
            self._barge_in_frame_count = 0
            self.wake_provider.reset()
            self.vad_provider.reset()
            if hasattr(self.audio_input, "clear"):
                self.audio_input.clear()
        elif new_state == AssistantState.SPEAKING:
            self._speaking_start_time = time.time()
            self._barge_in_frame_count = 0
        elif new_state in (AssistantState.LISTENING, AssistantState.ACTIVE_CONVERSATION):
            self._speech_buffer.clear()
            self._has_speech_started = False
            self._speech_frame_count = 0
            self._silence_frame_count = 0
            self._barge_in_frame_count = 0
            self.vad_provider.reset()
            # Drain lingering speaker echo from microphone queue
            if hasattr(self.audio_input, "clear"):
                self.audio_input.clear()
            if old_state == AssistantState.SPEAKING:
                # 350ms acoustic cooldown to let speaker resonance completely dissipate in room
                self._ignore_mic_until = time.time() + 0.35

    def start(self):
        """Start orchestrator and audio stream."""
        self._running = True
        self.audio_input.start()
        self.wake_provider.start()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()
        print("[Brown] Orchestrator started. Brown is SLEEPING (listening for wake word).")

    def stop(self):
        """Stop orchestrator cleanly."""
        self._running = False
        self.audio_output.interrupt()
        self.audio_input.stop()
        self.wake_provider.stop()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)
        print("[Brown] Orchestrator stopped.")

    def trigger_wake(self, reason: str = "manual_trigger"):
        """Programmatic trigger for wake word (useful for tests or buttons)."""
        self.state_machine.transition_to(AssistantState.WAKE_DETECTED, reason=reason)
        self._speak(self.greeting, next_state=AssistantState.LISTENING)

    def trigger_text_command(self, text: str):
        """Direct text injection for tests and non-voice CLI mode."""
        self.state_machine.transition_to(AssistantState.THINKING, reason="text_command")
        response_text = self._process_command(text)
        self._speak(response_text, next_state=AssistantState.ACTIVE_CONVERSATION)

    def _run_loop(self):
        """Main audio processing and state pump."""
        while self._running:
            # Check conversation timeouts
            self.state_machine.check_timeouts()

            chunk = self.audio_input.read_chunk(timeout=0.08)
            if chunk is None or len(chunk) == 0:
                continue

            state = self.state_machine.current_state

            # 1. SLEEPING: Dedicated wake-word detector only (STT dormant)
            if state == AssistantState.SLEEPING:
                detected = self.wake_provider.process_frame(chunk)
                if detected:
                    print(f"[Brown] Wake word '{detected}' detected!")
                    self.state_machine.transition_to(AssistantState.WAKE_DETECTED, reason=f"wake:{detected}")
                    self._speak(self.greeting, next_state=AssistantState.LISTENING)

            # 2. LISTENING: Monitor user speech via VAD
            elif state in (AssistantState.LISTENING, AssistantState.ACTIVE_CONVERSATION):
                if time.time() < self._ignore_mic_until:
                    continue

                is_speech = self.vad_provider.is_speech(chunk, sample_rate=self.audio_input.sample_rate)

                if is_speech:
                    if state == AssistantState.ACTIVE_CONVERSATION:
                        self.state_machine.transition_to(AssistantState.LISTENING, reason="follow_up_speech")

                    self._has_speech_started = True
                    self._speech_frame_count += 1
                    self._silence_frame_count = 0
                    self._speech_buffer.append(chunk)
                else:
                    if self._has_speech_started:
                        self._silence_frame_count += 1
                        self._speech_buffer.append(chunk)

                        # End of speech detected (silence threshold exceeded)
                        if self._silence_frame_count >= self.min_silence_frames:
                            if self._speech_frame_count >= self.min_speech_frames:
                                print("[Brown] Speech boundary complete, transitioning to THINKING.")
                                self.state_machine.transition_to(AssistantState.THINKING, reason="end_of_speech")
                                # Dispatch processing to worker thread to keep audio pump reactive
                                audio_copy = np.concatenate(self._speech_buffer)
                                threading.Thread(target=self._handle_transcription_and_action, args=(audio_copy,), daemon=True).start()
                            else:
                                # Too short to be meaningful speech (false trigger/click)
                                self._has_speech_started = False
                                self._speech_buffer.clear()
                                self._speech_frame_count = 0
                                self._silence_frame_count = 0

            # 3. SPEAKING: TTS is playing, check for barge-in with echo protection
            elif state == AssistantState.SPEAKING:
                if self.barge_in_enabled:
                    now = time.time()
                    # Only check barge-in after the grace period has passed (prevents speaker echo)
                    if now - self._speaking_start_time >= self.barge_in_grace_period_sec:
                        is_speech = self.vad_provider.is_speech(chunk, sample_rate=self.audio_input.sample_rate)
                        if is_speech:
                            self._barge_in_frame_count += 1
                            # Require sustained speech (at least min_frames) to trigger interruption
                            if self._barge_in_frame_count >= self.barge_in_min_frames:
                                print("[Brown] Barge-in speech detected! Halting TTS output immediately.")
                                self.audio_output.interrupt()
                                self.state_machine.transition_to(AssistantState.LISTENING, reason="barge_in_interruption")
                                self._speech_buffer.append(chunk)
                                self._has_speech_started = True
                                self._speech_frame_count = 1
                                self._silence_frame_count = 0
                        else:
                            self._barge_in_frame_count = max(0, self._barge_in_frame_count - 1)

    def _handle_transcription_and_action(self, audio_data: np.ndarray):
        """Transcribe speech and execute routed action."""
        try:
            print("[Brown] Transcribing audio with local STT...")
            text = self.stt_provider.transcribe(audio_data, sample_rate=self.audio_input.sample_rate)
            print(f"[Brown] User said: \"{text}\"")

            if not text.strip():
                print("[Brown] Empty transcription. Returning to ACTIVE_CONVERSATION.")
                self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="empty_transcript")
                return

            response_text = self._process_command(text)
            if response_text:
                self._speak(response_text, next_state=AssistantState.ACTIVE_CONVERSATION)
            else:
                self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="action_completed_quietly")

        except Exception as e:
            print(f"[Brown] Error during transcription/action: {e}")
            self._speak("Sorry, I encountered an issue processing that.", next_state=AssistantState.ACTIVE_CONVERSATION)

    def _process_command(self, text: str) -> str:
        """Route and execute command."""
        routed = self.intent_router.route(text)

        if routed.action_type == "stop":
            return "Stopped."

        elif routed.action_type == "tool_call":
            tool = self.tool_registry.get(routed.tool_name)
            if not tool:
                return f"Tool {routed.tool_name} is not available."

            args = routed.tool_args or {}
            print(f"[Brown] Executing typed tool: {routed.tool_name}({args})")
            result = tool.execute(**args)
            return result.message

        elif routed.action_type == "conversation":
            return routed.direct_response or "Understood."

        return "I heard you, but I'm not sure how to handle that yet."

    def _speak(self, text: str, next_state: AssistantState = AssistantState.ACTIVE_CONVERSATION):
        """Synthesize text and play through interruptible audio player."""
        self.state_machine.transition_to(AssistantState.SPEAKING, reason="speaking_response")
        print(f"[Brown] Speaking: \"{text}\"")

        try:
            audio_samples, sample_rate = self.tts_provider.synthesize(text)

            def _on_playback_complete():
                if self.state_machine.current_state == AssistantState.SPEAKING:
                    self.state_machine.transition_to(next_state, reason="playback_finished")

            self.audio_output.play(audio_samples, sample_rate, on_complete=_on_playback_complete)

        except Exception as e:
            print(f"[Brown] TTS synthesis error: {e}")
            self.state_machine.transition_to(next_state, reason="tts_error")
