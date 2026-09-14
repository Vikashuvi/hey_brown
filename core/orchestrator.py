import time
import threading
from typing import Optional, List, Any
import numpy as np

from core.state import StateMachine, AssistantState
from core.intent import DeterministicIntentRouter, RoutedAction
from core.device_resolver import DeviceResolver
from core.ai.router import AIRouter, RoutingDecision
from core.observability import RequestTrace
from core.events import BrownEvent, EventType
from tools.base import ToolRegistry
from voice.audio.base import AudioInput, AudioOutput
from voice.wake.base import WakeWordProvider
from voice.vad.base import VADProvider
from voice.stt.base import STTProvider
from voice.tts.base import TTSProvider
from voice.tts.speech_normalizer import SpeechNormalizer
from voice.audio.barge_in import AcousticBargeInDetector
from voice.audio.clause_buffer import ClauseBuffer


class BrownOrchestrator:
    """Core orchestrator for Brown.
    Coordinates audio I/O, wake word, VAD, STT, deterministic routing,
    three-tier AI routing, typed tools, TTS playback, and instant barge-in interruption.
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
        greeting: str = "Yeah?",
        event_bridge: Optional[Any] = None,
        brain: Optional[Any] = None,
        ai_router: Optional[AIRouter] = None,
        device_resolver: Optional[DeviceResolver] = None,
        auto_warm: bool = True,
        auto_start: bool = True,
    ):
        self.audio_input = audio_input
        self.audio_output = audio_output
        self.wake_provider = wake_provider
        self.vad_provider = vad_provider
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.tool_registry = tool_registry
        self.greeting = greeting
        self.event_bridge = event_bridge
        self.auto_warm = auto_warm
        self.auto_start = auto_start

        self.barge_in_enabled = True
        self.barge_in_grace_period_sec = 0.0  # Dynamic acoustic echo rejection replaces rigid delay
        self.barge_in_min_frames = 2          # Require ~160ms sustained speech to avoid click triggers
        self.speech_normalizer = SpeechNormalizer()
        self.barge_in_detector = AcousticBargeInDetector(min_interruption_frames=self.barge_in_min_frames)
        self.clause_buffer = ClauseBuffer(min_clause_words=3, max_clause_words=20)
        self._turn_cancel_event = threading.Event()
        self._turn_lock = threading.Lock()

        self.device_resolver = device_resolver or DeviceResolver()
        self.brain = brain
        self.intent_router = DeterministicIntentRouter(device_resolver=self.device_resolver)
        self.ai_router = ai_router or AIRouter(device_resolver=self.device_resolver)

        self.state_machine = StateMachine(
            conversation_timeout=conversation_timeout,
            on_state_change=self._on_state_change
        )

        self.min_speech_frames = int((min_speech_duration_ms / 1000.0) / 0.08)  # 80ms per chunk
        self.min_silence_frames = int((min_silence_duration_ms / 1000.0) / 0.08)

        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        self._lifecycle_thread: Optional[threading.Thread] = None
        self._last_ai_state: Optional[str] = None

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
        if self.event_bridge:
            self.event_bridge.broadcast("state_change", {
                "state": new_state.value,
                "old_state": old_state.value
            })

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
                # Acoustic cooldown only applies when speech ends naturally, not during user barge-in
                if not self._turn_cancel_event.is_set():
                    self._ignore_mic_until = time.time() + 0.35
                else:
                    self._ignore_mic_until = 0.0

    def interrupt_current_turn(self, reason: str = "barge_in") -> bool:
        """Centralized cancellation controller that aborts active generation,
        TTS synthesis, sounddevice audio playback, and resets turn state.
        """
        with self._turn_lock:
            # 1. Signal cancellation event to LLM token streaming and background tasks
            self._turn_cancel_event.set()

            # 2. Abort audio player hardware stream and clear queued chunks
            was_playing = self.audio_output.interrupt()

            # 3. Reset streaming clause buffer and barge-in detector
            self.clause_buffer.reset()
            self.barge_in_detector.reset()

            # 4. Don't ignore mic on barge-in
            self._ignore_mic_until = 0.0

            # 5. Transition state machine to LISTENING to immediately capture user speech
            if self.state_machine.current_state in (
                AssistantState.SPEAKING,
                AssistantState.THINKING,
                AssistantState.ACTIVE_CONVERSATION
            ):
                self.state_machine.transition_to(AssistantState.LISTENING, reason=reason)

            # 6. Emit event bridge notifications
            if self.event_bridge:
                self.event_bridge.broadcast("interrupted", {"reason": reason})
                self.event_bridge.broadcast("tts_speaking", {"speaking": False, "interrupted": True})

            return was_playing

    def start(self):
        """Start orchestrator and audio stream."""
        self._running = True
        if self.event_bridge:
            self.event_bridge.start()
        self.audio_input.start()
        self.wake_provider.start()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()
        self._lifecycle_thread = threading.Thread(target=self._run_local_ai_lifecycle, daemon=True)
        self._lifecycle_thread.start()
        print("[Brown] Orchestrator started. Brown is SLEEPING (listening for wake word).")

    def stop(self):
        """Stop orchestrator cleanly."""
        self._running = False
        self.audio_output.interrupt()
        self.audio_input.stop()
        self.wake_provider.stop()
        if self.event_bridge:
            self.event_bridge.stop()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)
        if self._lifecycle_thread and self._lifecycle_thread.is_alive():
            self._lifecycle_thread.join(timeout=1.0)
        print("[Brown] Orchestrator stopped.")

    def _run_local_ai_lifecycle(self):
        """Background thread monitoring Error Boy AI status, auto-warming, and emitting telemetry."""
        local_provider = getattr(self.ai_router, "local_provider", None)
        if not local_provider or not hasattr(local_provider, "get_health_state"):
            return

        has_warmed = False
        while self._running:
            try:
                status = local_provider.get_health_state()
                current_state = status.get("state", "OFFLINE")

                if current_state != self._last_ai_state:
                    self._last_ai_state = current_state
                    if self.event_bridge:
                        self.event_bridge.broadcast("local_ai_state_changed", status)

                # Auto-warm model if Error Boy is ready and auto_warm is enabled
                if self.auto_warm and not has_warmed and current_state == "READY":
                    if not status.get("loaded", False):
                        print(f"[Brown] Auto-warming local model {local_provider.model} on Error Boy...")
                        warm_res = local_provider.warm_model()
                        if warm_res.get("success"):
                            has_warmed = True
                            print(f"[Brown] Local model {local_provider.model} warmed and ready in memory.")
                            new_status = local_provider.get_health_state()
                            if self.event_bridge:
                                self.event_bridge.broadcast("local_ai_state_changed", new_status)
                    else:
                        has_warmed = True
            except Exception:
                pass

            # Non-blocking periodic interval
            for _ in range(10):
                if not self._running:
                    break
                time.sleep(0.5)

    def trigger_wake(self, reason: str = "manual_trigger"):
        """Programmatic trigger for wake word (useful for tests or buttons)."""
        self.state_machine.transition_to(AssistantState.WAKE_DETECTED, reason=reason)
        wake_greeting = self.greeting
        if self.brain and hasattr(self.brain, "behavior_layer") and self.brain.behavior_layer:
            wake_greeting = self.brain.behavior_layer.get_dynamic_wake_greeting()
        self._speak(wake_greeting, next_state=AssistantState.LISTENING)

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
                    wake_greeting = self.greeting
                    if self.brain and hasattr(self.brain, "behavior_layer") and self.brain.behavior_layer:
                        wake_greeting = self.brain.behavior_layer.get_dynamic_wake_greeting()
                    self._speak(wake_greeting, next_state=AssistantState.LISTENING)

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

                    if self.event_bridge:
                        amp = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0
                        self.event_bridge.broadcast("audio_active", {"active": True, "level": round(amp, 3)})
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

            # 3. SPEAKING: TTS is playing, check for barge-in with dynamic acoustic echo protection
            elif state == AssistantState.SPEAKING:
                if self.barge_in_enabled:
                    now = time.time()
                    if now - self._speaking_start_time >= self.barge_in_grace_period_sec:
                        is_speech = self.vad_provider.is_speech(chunk, sample_rate=self.audio_input.sample_rate)
                        self.barge_in_detector.min_interruption_frames = self.barge_in_min_frames
                        self.barge_in_detector.set_playback_active(self.audio_output.is_playing)
                        playback_rms = getattr(self.audio_output, "current_playback_rms", 0.0)
                        interrupted = self.barge_in_detector.evaluate_frame(
                            chunk,
                            is_vad_speech=is_speech,
                            playback_rms=playback_rms
                        )
                        if interrupted:
                            print("[Brown] Acoustic barge-in detected! Halting TTS output immediately.")
                            self.interrupt_current_turn(reason="barge_in_interruption")
                            self._speech_buffer.append(chunk)
                            self._has_speech_started = True
                            self._speech_frame_count = 1
                            self._silence_frame_count = 0

            # 4. THINKING: Monitor for speech interruption during AI generation
            elif state == AssistantState.THINKING:
                if self.barge_in_enabled:
                    is_speech = self.vad_provider.is_speech(chunk, sample_rate=self.audio_input.sample_rate)
                    if is_speech:
                        self._speech_frame_count += 1
                        if self._speech_frame_count >= self.min_speech_frames:
                            print("[Brown] User interrupted while thinking! Cancelling pending turn.")
                            self.interrupt_current_turn(reason="interrupted_during_thinking")
                            self._speech_buffer.append(chunk)
                            self._has_speech_started = True
                            self._silence_frame_count = 0
                    else:
                        self._speech_frame_count = max(0, self._speech_frame_count - 1)

    def _handle_transcription_and_action(self, audio_data: np.ndarray):
        """Transcribe speech and execute routed action with streaming clause synthesis and T0-T6 telemetry."""
        t_0 = time.time()  # T0: Audio chunk complete / transcription start
        self._turn_cancel_event.clear()
        try:
            print("[Brown] Transcribing audio with local STT...")
            text = self.stt_provider.transcribe(audio_data, sample_rate=self.audio_input.sample_rate)
            t_1 = time.time()  # T1: Transcription ready
            print(f"[Brown] User said: \"{text}\"")
            if self.event_bridge:
                self.event_bridge.broadcast("transcript", {"text": text, "is_final": True})

            if not text.strip():
                print("[Brown] Empty transcription. Returning to ACTIVE_CONVERSATION.")
                self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="empty_transcript")
                return

            if self._turn_cancel_event.is_set():
                print("[Brown] Turn cancelled after transcription.")
                return

            # Check Level 1 Deterministic Fast Path (e.g. stop / pause / cancel)
            fast_action = self.intent_router.match_fast_path(text)
            if fast_action and fast_action.action_type == "stop":
                print(f"[Brown] Stop command '{text}' received. Silencing immediately.")
                if self.event_bridge:
                    self.event_bridge.broadcast("reaction", {"mood": "neutral", "message": "Stopped."})
                self.audio_output.interrupt()
                self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="user_stop_command")
                return

            # Check Level 1 Pattern Matching for Identity / Local Memory Fast-Path (<0.1ms, zero LLM, zero quota)
            pattern_action = self.intent_router.match_pattern(text)
            if pattern_action and pattern_action.action_type == "memory_lookup":
                key = pattern_action.tool_name
                stored_val = None
                if self.brain and hasattr(self.brain, "memory_manager"):
                    rec = self.brain.memory_manager.store.get(key)
                    if rec:
                        stored_val = rec.value

                if key == "user_name":
                    response_text = f"Your name is {stored_val}." if stored_val else "I don't know your name yet. What should I call you?"
                elif key == "preferred_editor":
                    response_text = f"Your preferred editor is {stored_val}." if stored_val else "I don't have your preferred editor saved yet."
                elif key == "current_project":
                    response_text = f"You're working on {stored_val}." if stored_val else "I don't have a project name saved yet."
                else:
                    response_text = f"I have {key} saved as {stored_val}." if stored_val else "I don't have that information saved."

                print(f"[Brown] Memory Fast-Path resolved '{key}': \"{response_text}\" (<1ms, 0 quota)")
                self._speak(response_text, next_state=AssistantState.ACTIVE_CONVERSATION)
                return

            # Check Level 1 Pattern Matching for Deterministic Tool Call (<1ms, zero LLM, instant execution)
            if pattern_action and pattern_action.action_type == "tool_call":
                tool = self.tool_registry.get(pattern_action.tool_name)
                if tool:
                    target_dev = pattern_action.target_device or "paperball"
                    args = dict(pattern_action.tool_args or {})
                    if "device" not in args:
                        args["device"] = target_dev
                    tool_res = tool.execute(**args)

                    if self.brain and hasattr(self.brain, "context"):
                        self.brain.context.record_turn(
                            user_query=text,
                            response_text=tool_res.message,
                            tool_name=pattern_action.tool_name,
                            tool_args=args,
                            tool_result=tool_res.data or {},
                            success=tool_res.success,
                            verified=True,
                            device=target_dev
                        )
                        if "app_name" in args:
                            self.brain.context.active_app = args["app_name"]
                            self.brain.context.update_entity("app", args["app_name"])
                        self.brain.context.set_active_device(target_dev)

                    if self.event_bridge:
                        self.event_bridge.broadcast("tool_result", {
                            "tool": pattern_action.tool_name,
                            "success": tool_res.success,
                            "message": tool_res.message,
                            "data": tool_res.data
                        })

                    print(f"[Brown] Pattern Action executed '{pattern_action.tool_name}': \"{tool_res.message}\" (<10ms, 0 quota)")
                    self._speak(tool_res.message, next_state=AssistantState.ACTIVE_CONVERSATION)
                    return

            # Streaming via Conversational Brain if available
            if self.brain and hasattr(self.brain, "stream_query") and hasattr(self.audio_output, "queue_clause"):
                self._stream_brain_response(text, t_0, t_1)
                return

            # Non-streaming fallback
            response_text = self._process_command(text)
            if self._turn_cancel_event.is_set():
                print("[Brown] Turn cancelled after command processing.")
                return

            if response_text:
                self._speak(response_text, next_state=AssistantState.ACTIVE_CONVERSATION)
            else:
                self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="action_completed_quietly")

        except Exception as e:
            print(f"[Brown] Error during transcription/action: {e}")
            if self.event_bridge:
                self.event_bridge.broadcast("error", {"message": str(e)})
            if not self._turn_cancel_event.is_set():
                self._speak("Sorry, I encountered an issue processing that.", next_state=AssistantState.ACTIVE_CONVERSATION)

    def _stream_brain_response(self, text: str, t_0: float, t_1: float):
        """Execute Brain query with token streaming, clause segmentation, TTS normalization, and T0-T6 logging."""
        t_2 = time.time()  # T2: Intent/LLM query dispatched
        t_3 = None         # T3: First token received
        t_4 = None         # T4: First clause completed
        t_5 = None         # T5: First audio chunk synthesized
        t_6 = None         # T6: Playback started

        if self.event_bridge:
            self.event_bridge.broadcast("state_change", {"state": "THINKING", "description": "Processing..."})

        self.clause_buffer.reset()
        stream_started = False

        def _on_first_audio():
            nonlocal t_6
            t_6 = time.time()
            if self.event_bridge:
                self.event_bridge.broadcast("tts_speaking", {"speaking": True})
            stt_lat = round((t_1 - t_0) * 1000, 1)
            ttft = round(((t_3 or t_2) - t_2) * 1000, 1)
            clause_lat = round(((t_4 or t_2) - t_2) * 1000, 1)
            tts_lat = round(((t_5 or t_4 or t_2) - (t_4 or t_2)) * 1000, 1)
            ttfa = round((t_6 - t_0) * 1000, 1)
            print(f"[Brown Latency] T0->T6 Total TTFA: {ttfa}ms (STT: {stt_lat}ms, TTFT: {ttft}ms, Clause: {clause_lat}ms, TTS: {tts_lat}ms)")

        def _on_stream_complete():
            if self.event_bridge:
                self.event_bridge.broadcast("tts_speaking", {"speaking": False})
            if self.state_machine.current_state == AssistantState.SPEAKING:
                self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="stream_playback_finished")

        for token in self.brain.stream_query(text, cancel_event=self._turn_cancel_event):
            if self._turn_cancel_event.is_set():
                print("[Brown] Stream aborted mid-generation.")
                self.audio_output.interrupt()
                return

            if t_3 is None:
                t_3 = time.time()

            clauses = self.clause_buffer.append(token)
            for clause in clauses:
                if self._turn_cancel_event.is_set():
                    self.audio_output.interrupt()
                    return

                if t_4 is None:
                    t_4 = time.time()

                norm_clause = self.speech_normalizer.normalize(clause)
                if not norm_clause.strip():
                    continue

                try:
                    audio_data, sr = self.tts_provider.synthesize(norm_clause)
                    if self._turn_cancel_event.is_set():
                        self.audio_output.interrupt()
                        return

                    if t_5 is None:
                        t_5 = time.time()

                    if not stream_started:
                        stream_started = True
                        self.state_machine.transition_to(AssistantState.SPEAKING, reason="speaking_stream")
                        self.audio_output.play_clause_stream(
                            on_first_audio=_on_first_audio,
                            on_complete=_on_stream_complete
                        )

                    self.audio_output.queue_clause(audio_data, sr)
                except Exception as synth_err:
                    print(f"[Brown] Clause synthesis error: {synth_err}")

        # Flush any remaining tokens in buffer
        if not self._turn_cancel_event.is_set():
            remainder = self.clause_buffer.flush()
            if remainder:
                norm_rem = self.speech_normalizer.normalize(remainder)
                if norm_rem.strip():
                    try:
                        audio_data, sr = self.tts_provider.synthesize(norm_rem)
                        if not stream_started:
                            stream_started = True
                            self.state_machine.transition_to(AssistantState.SPEAKING, reason="speaking_stream")
                            self.audio_output.play_clause_stream(
                                on_first_audio=_on_first_audio,
                                on_complete=_on_stream_complete
                            )
                        self.audio_output.queue_clause(audio_data, sr)
                    except Exception as synth_err:
                        print(f"[Brown] Remainder synthesis error: {synth_err}")

        if hasattr(self.audio_output, "end_stream"):
            self.audio_output.end_stream()

        if not stream_started:
            self.state_machine.transition_to(AssistantState.ACTIVE_CONVERSATION, reason="empty_stream_result")

    def _process_command(self, text: str) -> str:
        """Route and execute command using 3-tier intelligence, tracing, and natural verification."""
        trace = RequestTrace()
        t_route_0 = time.time()

        # 1. Level 1 Deterministic Fast Path check (Emergency stop/cancel only)
        fast_action = self.intent_router.match_fast_path(text)
        if fast_action and fast_action.action_type == "stop":
            if self.event_bridge:
                self.event_bridge.broadcast("reaction", {"mood": "neutral", "message": "Stopped."})
            trace.intent_latency_ms = round((time.time() - t_route_0) * 1000, 2)
            trace.provider_used = "deterministic"
            trace.finish()
            trace.log_summary()
            return "Stopped."

        pattern_action = self.intent_router.match_pattern(text)
        if pattern_action and pattern_action.action_type == "memory_lookup":
            key = pattern_action.tool_name
            stored_val = None
            if self.brain and hasattr(self.brain, "memory_manager"):
                rec = self.brain.memory_manager.store.get(key)
                if rec:
                    stored_val = rec.value

            if key == "user_name":
                resp = f"Your name is {stored_val}." if stored_val else "I don't know your name yet. What should I call you?"
            elif key == "preferred_editor":
                resp = f"Your preferred editor is {stored_val}." if stored_val else "I don't have your preferred editor saved yet."
            elif key == "current_project":
                resp = f"You're working on {stored_val}." if stored_val else "I don't have a project name saved yet."
            else:
                resp = f"I have {key} saved as {stored_val}." if stored_val else "I don't have that information saved."

            trace.intent_latency_ms = round((time.time() - t_route_0) * 1000, 2)
            trace.provider_used = "memory_store"
            trace.finish()
            trace.log_summary()
            return resp

        if pattern_action and pattern_action.action_type == "tool_call":
            tool = self.tool_registry.get(pattern_action.tool_name)
            if tool:
                target_dev = pattern_action.target_device or "paperball"
                args = dict(pattern_action.tool_args or {})
                if "device" not in args:
                    args["device"] = target_dev
                tool_res = tool.execute(**args)
                trace.intent_latency_ms = round((time.time() - t_route_0) * 1000, 2)
                trace.provider_used = "deterministic"
                trace.tool_name = pattern_action.tool_name
                trace.target_device = target_dev
                trace.success = tool_res.success
                trace.finish()
                trace.log_summary()

                if self.brain and hasattr(self.brain, "context"):
                    self.brain.context.record_turn(
                        user_query=text,
                        response_text=tool_res.message,
                        tool_name=pattern_action.tool_name,
                        tool_args=args,
                        tool_result=tool_res.data or {},
                        success=tool_res.success,
                        verified=True,
                        device=target_dev
                    )
                    if "app_name" in args:
                        self.brain.context.active_app = args["app_name"]
                        self.brain.context.update_entity("app", args["app_name"])
                    self.brain.context.set_active_device(target_dev)

                if self.event_bridge:
                    self.event_bridge.broadcast("tool_result", {
                        "tool": pattern_action.tool_name,
                        "success": tool_res.success,
                        "message": tool_res.message,
                        "data": tool_res.data
                    })
                return tool_res.message

        # 2. Conversational Brain (PydanticAI)
        if self.brain:
            if self.event_bridge:
                self.event_bridge.broadcast("state_change", {"state": "THINKING", "description": "Processing..."})

            brain_resp = self.brain.process_query(text)
            trace.intent_latency_ms = brain_resp.latency_ms
            trace.provider_used = "pydantic_ai"
            trace.target_device = brain_resp.target_device
            trace.tool_name = brain_resp.tool_called
            trace.success = brain_resp.success

            if brain_resp.tool_called and self.event_bridge:
                self.event_bridge.broadcast("tool_result", {
                    "tool": brain_resp.tool_called,
                    "success": brain_resp.success,
                    "message": brain_resp.text,
                    "data": brain_resp.tool_result
                })

            if self.event_bridge:
                mood = "happy" if brain_resp.success else "concerned"
                self.event_bridge.broadcast("reaction", {"mood": mood, "message": brain_resp.text})
                self.event_bridge.broadcast("state_change", {"state": "HAPPY" if brain_resp.success else "CONCERNED"})

            trace.finish()
            trace.log_summary()
            if self.event_bridge:
                self.event_bridge.broadcast("trace_telemetry", trace.to_safe_dict())
            return brain_resp.text

        # 3. Legacy 3-Tier AI Router fallback
        deterministic_match = None
        if fast_action:
            deterministic_match = RoutingDecision(
                level=1,
                provider_used="deterministic",
                action_type=fast_action.action_type,
                tool_name=fast_action.tool_name,
                tool_args=fast_action.tool_args,
                direct_response=fast_action.direct_response,
                target_device=fast_action.target_device,
                confidence=fast_action.confidence,
            )

        decision = self.ai_router.route_and_execute_intent(
            query=text,
            deterministic_match=deterministic_match
        )
        trace.intent_latency_ms = round((time.time() - t_route_0) * 1000, 2)
        trace.provider_used = decision.provider_used
        trace.target_device = decision.target_device
        trace.fallback_reason = decision.fallback_reason

        # Avatar feedback for thinking state
        if self.event_bridge:
            if decision.level == 2:
                self.event_bridge.broadcast("state_change", {"state": "THINKING", "description": "Analyzing..."})
            elif decision.level == 3:
                self.event_bridge.broadcast("state_change", {"state": "THINKING", "description": "Cloud reasoning..."})

        # 3. Action execution
        if decision.action_type == "stop":
            if self.event_bridge:
                self.event_bridge.broadcast("reaction", {"mood": "neutral", "message": "Stopped."})
            trace.finish()
            trace.log_summary()
            return "Stopped."

        elif decision.action_type == "tool_call":
            trace.tool_name = decision.tool_name
            tool = self.tool_registry.get(decision.tool_name)
            if not tool:
                trace.success = False
                trace.error_message = f"Tool {decision.tool_name} not found"
                if self.event_bridge:
                    self.event_bridge.broadcast("state_change", {"state": "CONFUSED"})
                    self.event_bridge.broadcast("reaction", {"mood": "confused", "message": f"Tool {decision.tool_name} is not available."})
                trace.finish()
                trace.log_summary()
                return f"Tool {decision.tool_name} is not available."

            args = decision.tool_args or {}
            target_device = decision.target_device or args.get("device", "paperball")
            display_name = self.device_resolver.get_display_name(target_device)

            # Avatar feedback if waiting on remote device
            if self.event_bridge:
                desc = f"Waiting for {display_name}..." if target_device != self.device_resolver.default_local_device else f"Executing {decision.tool_name}"
                self.event_bridge.broadcast("state_change", {
                    "state": "EXECUTING",
                    "description": desc,
                    "tool": decision.tool_name,
                    "device": target_device
                })

            # Execute tool with timing
            t_tool_0 = time.time()
            result = tool.execute(**args)
            trace.tool_latency_ms = round((time.time() - t_tool_0) * 1000, 2)
            trace.success = result.success

            # Verification & Natural Conversational Synthesis
            final_message = result.message
            if result.success and decision.tool_name == "get_system_status" and result.data:
                data = result.data
                load = data.get("load1") or data.get("cpu_usage") or 0.0
                ram_pct = data.get("ram_usage_pct") or data.get("memory_usage") or 0.0
                gpu_temp = data.get("gpu_temperature") or data.get("gpu_temp")
                temp_str = f", and GPU temperature is {gpu_temp}°C" if gpu_temp else ""
                final_message = f"{display_name} is online and healthy. CPU load is around {load}, memory is at {ram_pct}%{temp_str}."

            elif result.success and decision.tool_name == "get_running_apps" and result.data:
                apps = result.data.get("running_apps", [])
                if apps:
                    final_message = f"On {display_name}, the running applications are: {', '.join(apps)}."
                else:
                    final_message = f"There are no major applications currently running on {display_name}."

            if self.event_bridge:
                self.event_bridge.broadcast("tool_result", {
                    "tool": decision.tool_name,
                    "success": result.success,
                    "message": final_message,
                    "data": result.data if hasattr(result, "data") else None
                })
                self.event_bridge.broadcast("state_change", {
                    "state": "HAPPY" if result.success else "CONCERNED"
                })
                self.event_bridge.broadcast("reaction", {
                    "mood": "happy" if result.success else "concerned",
                    "message": final_message
                })

            # Record turn in conversational context for follow-up continuity
            self.ai_router.context.add_turn(
                user_query=text,
                response_text=final_message,
                target_device=target_device,
                tool_name=decision.tool_name,
                tool_result=result.data if hasattr(result, "data") else None
            )

            trace.finish()
            trace.log_summary()
            if self.event_bridge:
                self.event_bridge.broadcast("trace_telemetry", trace.to_safe_dict())
            return final_message

        elif decision.action_type == "conversation":
            response = decision.direct_response or "Understood."
            if self.event_bridge:
                self.event_bridge.broadcast("reaction", {"mood": "happy", "message": response})
            self.ai_router.context.add_turn(
                user_query=text,
                response_text=response,
                target_device=decision.target_device
            )
            trace.finish()
            trace.log_summary()
            if self.event_bridge:
                self.event_bridge.broadcast("trace_telemetry", trace.to_safe_dict())
            return response

        # Fallback
        msg = "I heard you, but I'm not sure how to handle that yet."
        if self.event_bridge:
            self.event_bridge.broadcast("reaction", {"mood": "confused", "message": msg})
        trace.finish()
        trace.log_summary()
        return msg


    def _speak(self, text: str, next_state: AssistantState = AssistantState.ACTIVE_CONVERSATION):
        """Synthesize normalized text and play through interruptible audio player."""
        if not text or not text.strip():
            return

        # Normalize Markdown formatting, bullets, URLs, symbols, units to natural spoken words
        spoken_text = self.speech_normalizer.normalize(text)
        if not spoken_text.strip():
            return

        if self._turn_cancel_event.is_set():
            print("[Brown] Turn cancelled prior to speak dispatch.")
            return

        self.state_machine.transition_to(AssistantState.SPEAKING, reason="speaking_response")
        print(f"[Brown] Speaking: \"{spoken_text}\"")
        if self.event_bridge:
            self.event_bridge.broadcast("tts_speaking", {"text": spoken_text, "speaking": True})

        try:
            audio_samples, sample_rate = self.tts_provider.synthesize(spoken_text)

            if self._turn_cancel_event.is_set():
                print("[Brown] Turn cancelled prior to playback start.")
                return

            def _on_playback_complete():
                if self.event_bridge:
                    self.event_bridge.broadcast("tts_speaking", {"speaking": False})
                if self.state_machine.current_state == AssistantState.SPEAKING:
                    self.state_machine.transition_to(next_state, reason="playback_finished")

            self.audio_output.play(audio_samples, sample_rate, on_complete=_on_playback_complete)

        except Exception as e:
            print(f"[Brown] TTS synthesis error: {e}")
            if self.event_bridge:
                self.event_bridge.broadcast("tts_speaking", {"speaking": False, "error": str(e)})
            self.state_machine.transition_to(next_state, reason="tts_error")
