# Brown AI Assistant — Project Progress & Development Log

> This document tracks all architectural milestones, completed features, ongoing updates, and the project roadmap. Whenever a new feature, bug fix, or optimization is implemented, this file is updated to maintain a living record of Brown's evolution.

---

## 📋 Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Chronological Development Log](#chronological-development-log)
   - [Milestone 1 — Initial Core Voice Pipeline (V1 Voice Slice)](#milestone-1--initial-core-voice-pipeline-v1-voice-slice)
   - [Milestone 2 — Performance Tuning & Multi-Agent Architecture](#milestone-2--performance-tuning--multi-agent-architecture)
   - [Milestone 3 — Interactive Testing & Voice Preview Utilities](#milestone-3--interactive-testing--voice-preview-utilities)
   - [Milestone 4 — Robust Barge-In & Acoustic Echo Protection](#milestone-4--robust-barge-in--acoustic-echo-protection)
   - [Milestone 5 — Configurable Wake Phrases & Natural Intent Routing](#milestone-5--configurable-wake-phrases--natural-intent-routing)
   - [Milestone 6 — Error Boy (Arch Linux) Remote Operation](#milestone-6--error-boy-arch-linux-remote-operation)
   - [Milestone 7 — Living Desktop Mascot UI (feral-blob)](#milestone-7--living-desktop-mascot-ui-feral-blob)
   - [Milestone 8 — Generic Device Architecture, Pluggable AI Runtime, Cross-Device Data & Clause Streaming [CURRENT]](#milestone-8--generic-device-architecture-pluggable-ai-runtime-cross-device-data--clause-streaming-current)
3. [Test Suite Status](#test-suite-status)
4. [Upcoming Roadmap](#upcoming-roadmap)


---

## 🏗️ System Architecture Overview

Brown operates as a dual-machine, multimodal voice assistant distributed across two hardware environments:

```
                      ┌─────────────────────────────────────────┐
                      │            BROWN CONTROLLER             │
                      │  Voice Engine / State Machine / Router  │
                      └────────────────────┬────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
       ┌────────────────────────┐                    ┌────────────────────────┐
       │     PAPERBALL AGENT    │                    │     ERROR BOY AGENT    │
       │   Primary Device: Mac  │                    │ Secondary: Arch Linux  │
       │  (Microphone / Speaker │                    │  (High Compute / Apps /│
       │     macOS Desktop)     │                    │     Local LLM Node)    │
       └────────────────────────┘                    └────────────────────────┘
```

---

## 📜 Chronological Development Log

### Milestone 1 — Initial Core Voice Pipeline (V1 Voice Slice)
* **Goal**: Establish the zero-latency, local-first voice capture, transcription, and speech synthesis loop.
* **Accomplishments**:
  * **Audio Capture & Streaming** (`voice/audio/stream.py`): Developed a non-blocking PyAudio stream capturing mono audio at 16kHz with circular ring buffering to prevent memory leakage.
  * **Voice Activity Detection (VAD)** (`voice/vad/silero_vad.py`): Integrated Silero VAD v5 with sliding-window analysis and customizable silence thresholds (1300ms natural speech window).
  * **Speech-to-Text (STT)** (`voice/stt/whisper_stt.py`): Integrated `faster-whisper` using 8-bit quantized models (`base.en` / `tiny.en`) for real-time local transcription.
  * **Text-to-Speech (TTS)** (`voice/tts/kokoro_tts.py`): Deployed `kokoro-onnx` (82M parameters) delivering human-like voice synthesis with custom voice models.
  * **Asynchronous State Machine** (`core/state.py`): Built thread-safe state management (`SLEEPING`, `LISTENING`, `PROCESSING`, `SPEAKING`, `ACTIVE_CONVERSATION`, `ERROR`).
  * **Master Orchestrator** (`core/orchestrator.py`): Connected audio input $\rightarrow$ VAD $\rightarrow$ STT $\rightarrow$ routing $\rightarrow$ TTS into a continuous execution loop.

---

### Milestone 2 — Performance Tuning & Multi-Agent Architecture
* **Goal**: Decouple device commands from the core loop and optimize hot-path processing.
* **Accomplishments**:
  * **Circular Dependency Resolution**: Refactored `agents/` and `devices/` packages, introducing `DeviceAgent` abstract base class and strict typed interfaces (`DeviceCommandResult`, `ToolResult`).
  * **Paperball macOS Agent** (`agents/paperball.py`): Implemented safe local application launch (`open -a`), application closing (AppleScript), browser URL handling, and system status metrics.
  * **Error Boy Agent Client** (`agents/error_boy.py`): Created resilient HTTP client connecting to Error Boy's REST endpoint with graceful offline fallback (never stalls Paperball if Error Boy is powered off or unreachable).
  * **Intent Routing Engine** (`core/intent.py`): Replaced runtime string searches with precompiled regular expressions for sub-millisecond dispatch.

---

### Milestone 3 — Interactive Testing & Voice Preview Utilities
* **Goal**: Provide CLI tooling to audition components without running the complete mic-and-speaker loop.
* **Accomplishments**:
  * **Interactive Quick Test Suite** (`scripts/demo_quick_test.py`):
    * Wake word simulation with synthetic audio.
    * Text-to-Intent interactive sandbox.
    * End-to-end simulated voice turn.
  * **Voice Preview Tool** (`scripts/preview_voices.py`):
    * Audition Kokoro voices (`af_bella`, `af_heart`, `af_nicole`, `af_sarah`, `am_adam`, `bm_george`, etc.).
    * Audio preview generation and playback directly from CLI.

---

### Milestone 4 — Robust Barge-In & Acoustic Echo Protection
* **Goal**: Allow users to naturally interrupt Brown while speaking without acoustic loopback (preventing the assistant from hearing its own voice).
* **Accomplishments**:
  * **Instant Barge-In Cancellation** (`voice/audio/player.py`):
    * Audio player playback loop checks cancellation tokens on every frame chunk, cutting output instantly when user speaks.
  * **Acoustic Feedback Shield**:
    * Added **Barge-In Grace Period** (`1.2s`) to ignore microphone feedback at the immediate onset of audio playback.
    * Implemented **Acoustic Cooldown (350ms)** upon transitioning from `SPEAKING` to `LISTENING` to let room reverberation clear.
    * Flushed lingering audio queue buffers at state transition boundaries.

---

### Milestone 5 — Configurable Wake Phrases & Natural Intent Routing
* **Goal**: Allow custom wake words and flexible natural language command phrasing.
* **Accomplishments**:
  * **Native Brown Wake Provider** (`voice/wake/brown_wake_provider.py`):
    * Energy and VAD pre-filtering combined with phonetic similarity matching.
    * Centralized configuration in `config/default.yaml`.
  * **Configurable Wake Phrases**:
    * Enabled triggers: `"brown"`, `"hey brown"`, `"wake up brown"`, `"daddy is home"`, `"hello brown"`, `"yo brown"`.
  * **Intent Router Flexibility**:
    * Expanded app names, web domains, and natural spoken forms.

---

### Milestone 6 — Error Boy (Arch Linux) Controlled HTTP Capability Agent
* **Goal**: Enable reliable, bounded, and typed remote operation of the secondary Arch Linux machine (HP Victus) from Brown on Paperball (macOS) via HTTP REST.
* **Architecture Principles**:
  * **No Unrestricted Shell Access**: Brown does not expose arbitrary command execution to models or users. All actions are strictly bounded, typed capabilities.
  * **Transport & Security**: Small authenticated HTTP service with optional bearer tokens, short timeouts (2.0s), and graceful offline error isolation so Paperball never freezes.
  * **Admin Boundaries**: SSH is reserved exclusively for system administration, setup, troubleshooting, and dev operations.
* **Typed Capabilities Implemented**:
  1. `get_device_status` (`/system/status` or `/status`): CPU load, RAM usage, hostname, and OS metrics.
  2. `get_running_apps` (`/apps/running`): Safe, non-root inspection of active desktop processes.
  3. `open_application` (`/apps/open`): Strict input validation (`^[a-zA-Z0-9\s\-_\.]+$`, length $\le 64$), binary resolution, Wayland/X11 session forwarding (`DISPLAY=:0`), and uninstalled binary reporting.
  4. `open_url` (`/browser/open`): URL scheme validation (`http`/`https` only, length $\le 2048$), multi-platform launcher (`xdg-open` / browser).
  5. `get_device_capabilities` (`/capabilities`): Machine metadata and supported capability discovery.
* **Component Deliverables**:
  * **Error Boy Daemon Server** (`devices/error_boy_server.py`): Zero-dependency Python 3 HTTP service.
  * **Error Boy Client Agent** (`agents/error_boy.py`): Non-blocking HTTP client with 2.0s timeout and offline recovery.
  * **Paperball Client Agent** (`agents/paperball.py`): Native macOS implementation of the same 5 typed capabilities.
  * **Intent Routing** (`core/intent.py`): Natural language parsing for running apps, capabilities, status, and app launching across `"on arch"`, `"on linux"`, `"on secondary machine"`, and `"on error boy"`.
  * **systemd User Service** (`devices/brown-error-boy.service`): Persistent boot service installed, enabled, and actively running on Error Boy (`systemctl --user enable --now brown-error-boy.service`).
  * **Live Hardware Discovery Recorded (Master Spec Phase 1)**:
    * **CPU**: AMD Ryzen 5 5600H (12 threads @ up to 4.2GHz).
    * **RAM**: 7.1 GiB physical memory + 11.0 GiB zram/swap.
    * **GPU**: Dedicated NVIDIA GeForce GTX 1650 Mobile (4GB GDDR6 VRAM) + Integrated AMD Radeon Vega.
    * **OS / Desktop**: Arch Linux (Kernel 7.1.5-arch1-2), Hyprland Wayland compositor (`wayland-1`, `DISPLAY=:0`), Fish shell, Python 3.14.6.
  * **Privacy Shield**:
    * Clean generic `config/default.yaml` for public Git. Private LAN IP override isolated in `.gitignore`d `config/local.yaml`.
  * **Live Verification**:
    * Verified live HTTP REST connection between Paperball (macOS) and Error Boy (Arch Linux) across `get_device_status`, `get_running_apps`, and `get_device_capabilities`.

---

### Milestone 7 — Native macOS Menu-Bar Presence & Transparent Floating Overlay [CURRENT]
* **Goal**: Deliver a native macOS AI presence for Brown where the assistant lives in the macOS menu bar during idle and smoothly transitions to a transparent, borderless floating overlay near the top-right of the screen upon wake word detection.
* **Visual Identity & Feral-Blob Library Integration**:
  * **Signature `#D9829D` Berry / Rose-Quartz Jelly Palette**: Tailored CSS tokens (`--jelly-body-mid: #d9829d`, luminous top `--jelly-body-top: #fce2ec`, deep base `--jelly-body-deep: #99405d`, cheek glow `--jelly-cheek: #ff9ec0`).
  * **Official `BlobSpeech` Cloud Dialog Box**: Mounted directly above the mascot with the downward directional tail pointing to the jelly's crown, displaying live speech, transcripts, and qualitative states with animated SVG morphing.
  * **Roving Gaze & Micro-Stuttering**: Emotive saccade cycle during `THINKING` (looking down, micro-stutter adjust, thoughtful glance up, imperative double-blink) and attentive upward tilt during `LISTENING`.
  * **Offline Auto-Dismiss**: When disconnected from core, the overlay automatically hides after 12 seconds so it never remains stuck on the desktop.
* **Key Architecture & Design Decisions**:
  * **No Application Window / No Dock Icon**: Packaged as a native macOS accessory agent (`LSUIElement = true`) using Swift + Cocoa + WebKit. Enforces a single-instance guard to prevent duplicate icons.
  * **Custom Scheme Handler (`brown://app/`)**: Implemented `WKURLSchemeHandler` in Swift to eliminate WebKit `file://` CORS restrictions, ensuring ES6 modules and WebSockets load reliably.
  * **Direct Core Sync**: Dual-channel synchronization via native Swift WebSocket client on `ws://127.0.0.1:8766` and WebKit message handler.
  * **Zero-Chrome Transparent Overlay**: Floating `NSPanel` (`styleMask = [.borderless, .nonactivatingPanel]`, `level = .statusBar`).

* **Deliverables**:
  1. **Native Swift Shell** (`macos/BrownNative/main.swift`):
     * Native `NSStatusItem` in the system menu bar with vector jelly icon.
     * Non-activating transparent `NSPanel` with auto-repositioning for multi-display setups.
     * Bi-directional script message bridge between WebKit and Swift.
  2. **React + feral-blob Bundle** (`ui/`):
     * Frameless overlay stage with warm amber/chestnut palette.
     * TypeScript build configured with `base: './'` for local disk loading via `file://`.
  3. **Build & Bundler Script** (`scripts/build_macos_app.sh`):
     * Compiles native binary with `swiftc -O` and packages into standalone `Brown.app`.
  4. **macOS Login Auto-Start** (`scripts/com.brown.ui.plist` & `scripts/install_launch_agent.sh`):
     * Directly launches native `Brown.app` binary upon macOS user login.

---

### Milestone 8 — Generic Device Architecture, Pluggable AI Runtime, Cross-Device Data & Clause Streaming [CURRENT]
* **Goal**: Decouple Brown from any specific personal hardware or fixed machine identities, implementing an open-source platform supporting $N$ user-configured devices with typed capabilities, pluggable local AI engines, secure cross-device clipboard & file sync, and clause-level streaming speech.
* **Accomplishments**:
  * **Generic Device Registry & Records** (`core/device_resolver.py`):
    * Implemented structured `DeviceRecord` model with capabilities, roles, operating systems, and connection states.
    * Added query methods (`find_devices_by_capability`, `find_devices_by_role`, `find_device_for_local_ai`).
    * De-personalized PydanticAI system prompt in `core/ai/brain.py` to dynamically inject device summaries from the active registry.
  * **Unified Device Abstraction** (`agents/base.py` & `devices/base.py`):
    * Unified `DeviceAgent` and `DeviceCommandResult` across packages with zero duplicate interfaces.
  * **Pluggable Local AI Runtime** (`core/ai/runtime.py`):
    * Created `LocalInferenceRuntime(ABC)` with `OllamaRuntime` and `OpenAICompatibleRuntime` (for llama.cpp / vLLM).
    * Dynamic device resolution in `core/ai/local_provider.py` reading inference URL and device ID dynamically from the configured device.
  * **Cross-Device Clipboard Sync** (`agents/local_agent.py`, `devices/remote_daemon.py`, `tools/system_tools.py`):
    * Native macOS (`pbcopy`/`pbpaste`) and Linux (`wl-copy`/`wl-paste`/`xclip`) clipboard read/write with 512KB size limits.
    * Implemented `GetClipboardTool`, `SetClipboardTool`, and `SyncClipboardTool`.
  * **Secure Sandboxed File Transfer** (`agents/local_agent.py`, `devices/remote_daemon.py`, `tools/system_tools.py`):
    * Path traversal rejection (`..`, leading `/`, `\`), SHA-256 cryptographic checksums, atomic `.tmp` file rename, and 50MB size limits.
    * Implemented `TransferFileTool`.
  * **Clause-Level Streaming Pipeline** (`voice/audio/clause_buffer.py`):
    * Incremental token buffer extracting complete spoken clauses on punctuation boundaries (`.`, `!`, `?`, `;`, `,`) with abbreviation preservation.
  * **Turn Pipeline Latency Telemetry** (`core/observability.py`):
    * High-precision $T_0 \dots T_6$ milestone recording, measuring `time_to_first_token_ms`, `time_to_first_clause_ms`, and `time_to_first_audio_ms`.

---

## 🧪 Test Suite Status

All unit and integration tests pass cleanly across 21 test modules:

| Test File | Coverage / Purpose | Status |
|:---|:---|:---:|
| `tests/test_generic_device_registry.py` | $N$-device registration, capability queries, dynamic prompt summary | ✅ PASS (5/5) |
| `tests/test_local_ai_runtime.py` | `OllamaRuntime`, `OpenAICompatibleRuntime`, dynamic device resolution | ✅ PASS (4/4) |
| `tests/test_local_ai_lifecycle.py` | Local AI warm, idle unload, resource checks, OpenAI compatibility | ✅ PASS (8/8) |
| `tests/test_clipboard_and_file_transfer.py` | Cross-device clipboard, path traversal defense, checksum atomic writes | ✅ PASS (7/7) |
| `tests/test_clause_streaming.py` | ClauseBuffer token chunking, boundary parsing, $T_0 \dots T_6$ telemetry | ✅ PASS (5/5) |
| `tests/test_conversational_brain.py` | PydanticAI multi-turn reasoning, typed tools, offline device handling | ✅ PASS (5/5) |
| `tests/test_device_agents.py` | Local host and remote capability agents | ✅ PASS (5/5) |
| `tests/test_remote_daemon.py` | Linux daemon REST endpoints, auth tokens, system health | ✅ PASS (3/3) |
| `tests/test_ai_router.py` | Local vs cloud routing and privacy policy checks | ✅ PASS (6/6) |
| `tests/test_intent_router.py` | Dynamic alias and device intent matching | ✅ PASS (5/5) |
| `tests/test_natural_language_intent.py` | Freeform intent parsing with DeviceResolver | ✅ PASS (5/5) |
| `tests/test_settings.py` | Persistent JSON settings, thread safety, defaults | ✅ PASS (2/2) |
| `tests/test_observability.py` | Trace correlation IDs, secret masking, metrics | ✅ PASS (2/2) |
| `tests/test_state_machine.py` | Valid state machine transitions & locks | ✅ PASS (2/2) |
| `tests/test_audio_pipeline.py` | PyAudio ring buffers & mono 16kHz capture | ✅ PASS (1/1) |
| `tests/test_barge_in.py` | Frame-level playback cancellation & echo shields | ✅ PASS (2/2) |
| `tests/test_brown_wake.py` | Configurable wake phrases & phonetic triggers | ✅ PASS (3/3) |
| `tests/test_wake_calibration.py` | Acoustic energy calibration & ambient noise rejection | ✅ PASS (3/3) |
| `tests/test_event_bridge.py` | Thread-safe WebSocket mascot broadcast bridge | ✅ PASS (1/1) |
| `tests/test_live_models.py` | Silero VAD v5 & Faster-Whisper model loading | ✅ PASS (2/2) |
| `tests/test_orchestrator.py` | Full orchestrator lifecycle loop | ✅ PASS (2/2) |

**Current Score:** **78 / 78 Tests Passing** (100%)


---

## 🗺️ Upcoming Roadmap

1. **Local LLM Node on Error Boy**: Leverage Error Boy's GTX 1650 (4GB VRAM) for local GGUF / Ollama inference for complex reasoning tasks.
2. **Cross-Machine File & Clipboard Sync**: Allow sending files, code snippets, or clipboard contents between Paperball and Error Boy.
3. **Hardware & Peripheral Control**: Support hardware sensors and automated scripts.
4. **Hermes Task Execution**: Multi-step autonomous task planning using typed device capabilities.

