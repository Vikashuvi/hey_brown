# 🇮🇳 Brown — Personal AI Computer Assistant

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-17%20Passed-success.svg)](tests/)
[![Voice](https://img.shields.io/badge/Voice-Kokoro--82M%20ONNX-orange.svg)](https://github.com/thewh1teagle/kokoro-onnx)
[![Whisper](https://img.shields.io/badge/STT-Faster--Whisper-purple.svg)](https://github.com/SYSTRAN/faster-whisper)

> **Brown** is a voice-first, goal-oriented personal AI assistant inspired by the concept of **JARVIS**. Built as an open-source initiative from India, Brown is designed to operate seamlessly across computers, reason about tasks, automate workflows, and communicate through natural human voice.

---

## 🌟 Vision

Brown is not a basic chatbot or command-matching wrapper. The core operating principle is:

$$\text{Voice} \longrightarrow \text{Understanding} \longrightarrow \text{Planning} \longrightarrow \text{Action} \longrightarrow \text{Verification} \longrightarrow \text{Natural Voice Response}$$

Rather than teaching Brown only how to execute literal commands, **Brown chooses the most efficient and reliable workflow to accomplish a user's goal.**

---

## ⚡ Key Capabilities & Highlights

- **🎙️ Dedicated Continuous Wake-Word Detection:** Runs on `<1%` CPU using `openWakeWord` (ONNX). STT and heavy intelligence stay dormant until Brown is activated.
- **🗣️ Hyper-Realistic Human Voice (100% Local):** Integrated with `Kokoro-82M` (ONNX) using the warm, calm British `bm_george` persona (JARVIS style). Completely offline and free.
- **⚡ Instant Hardware Barge-In / Interruption:** If you interrupt or say *"Stop"* while Brown is speaking, audio output aborts instantly via hardware DAC buffer cancellation (`stream.abort()`).
- **🔄 Multi-Turn Conversational State:** Brown maintains an active conversational window (default: 8s) after answering, allowing natural follow-ups without repeating the wake word.
- **🖥️ Cross-Device Architecture:** 
  - **Paperball** (macOS) serves as the primary voice interface, app launcher, and browser controller.
  - **Error Boy** (Arch Linux) serves as the compute node for heavy local model inference, coding, and remote workflows.
  - Paperball operates 100% independently if Error Boy is offline.
- **🔒 Security & Typed Actions:** The AI agent never receives unrestricted shell access. Every action goes through strictly typed and validated tools (`open_application`, `open_url`, `get_system_status`).
- **⚡ Zero-LLM Deterministic Dispatch:** Simple commands like *"open Safari"* or *"open YouTube"* route immediately to tools in $<1$ms without unnecessary LLM overhead.

---

## 🏗️ Architecture

```text
                             [ MICROPHONE ]
                                   │
                                   ▼
                   ┌────────────────────────────────┐
                   │   Lightweight Wake Detector    │  < 1% CPU
                   │      (openWakeWord ONNX)       │
                   └───────────────┬────────────────┘
                                   │ "Hey Jarvis" / "Hey Brown"
                                   ▼
                   ┌────────────────────────────────┐
                   │           Silero VAD           │  Sub-millisecond
                   │   (Speech boundary detection)  │
                   └───────────────┬────────────────┘
                                   │ User Speech
                                   ▼
                   ┌────────────────────────────────┐
                   │       Faster-Whisper STT       │  ~120-150ms
                   │      (base.en / int8 CPU)      │
                   └───────────────┬────────────────┘
                                   │ Transcribed Text
                                   ▼
                   ┌────────────────────────────────┐
                   │   Deterministic Intent Router  │  < 1ms
                   │    (Zero-LLM fast path tools)  │
                   └───────────────┬────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
         ┌─────────────────────┐       ┌─────────────────────┐
         │   Paperball Agent   │       │   Error Boy Agent   │
         │     (Local macOS)   │       │  (Remote Arch Linux)│
         └──────────┬──────────┘       └──────────┬──────────┘
                    │                             │
                    └──────────────┬──────────────┘
                                   │ Result
                                   ▼
                   ┌────────────────────────────────┐
                   │        Kokoro-82M TTS          │  ~200ms
                   │   (bm_george / JARVIS voice)   │
                   └───────────────┬────────────────┘
                                   │ Audio Chunks
                                   ▼
                   ┌────────────────────────────────┐
                   │    Interruptible Audio Player  │
                   │   (Instant Hardware Barge-In)  │
                   └───────────────┬────────────────┘
                                   │
                                   ▼
                              [ SPEAKER ]
```

---

## ⏱️ Efficiency & Latency Profile

Tested on an 8-Core / 16-Thread CPU:

| Component | Engine | Latency | Resource Overhead |
| :--- | :--- | :--- | :--- |
| **Wake Detection** | `openWakeWord` (ONNX) | ~80ms / chunk | $<1\%$ CPU |
| **Voice Activity** | `Silero VAD` (ONNX) | $<1$ms | Negligible |
| **Speech-to-Text** | `faster-whisper` (`base.en` int8) | ~120–150ms | 4 threads |
| **Intent Dispatch** | Deterministic Regex Router | $<1$ms | 0 LLM tokens |
| **Speech Synthesis**| `Kokoro-82M` (ONNX) | ~200ms | CPU vectorized |
| **Barge-In Abort**  | `sounddevice.OutputStream.abort()`| Instant ($<10$ms) | Hardware DAC level |

---

## 🚀 Quick Start

### 1. Prerequisites

- **macOS** or **Linux**
- Python 3.10+ (Recommended: Python 3.11)
- PortAudio & FFmpeg:
  ```bash
  # macOS (Homebrew)
  brew install portaudio ffmpeg

  # Linux (Arch)
  sudo pacman -S portaudio ffmpeg

  # Linux (Debian/Ubuntu)
  sudo apt-get install -y portaudio19-dev ffmpeg
  ```

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Vikashuvi/hey_brown.git
cd hey_brown

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Brown

```bash
PYTHONPATH=. python main.py
```

On launch, Brown pre-warms all neural models in memory. When you speak:
1. **Activate:** Say **"Hey Jarvis"** (or configured wake word).
2. **Brown answers:** *"Yeah, I'm here. What can I do for you?"*
3. **Command:** Say **"Open Safari"** or **"Open YouTube"** or **"What is the status of Paperball?"**
4. **Barge-in:** While Brown is speaking, start talking or say *"Stop"*. Brown immediately cuts audio and listens.

---

## 🧪 Running Tests

Brown includes a comprehensive automated test suite covering state transitions, device security boundaries, URL validation, offline fallback, barge-in hardware cancellation, and live model inference:

```bash
PYTHONPATH=. pytest tests/ -v
```

```text
============================= 17 passed in 10.61s ==============================
```

---

## 📁 Repository Structure

```text
hey_brown/
├── config/
│   └── default.yaml          # Audio rates, thresholds, timeouts, device endpoints
├── core/
│   ├── state.py              # Conversational StateMachine (SLEEPING -> ACTIVE -> SLEEPING)
│   ├── intent.py             # DeterministicIntentRouter (zero-LLM fast path)
│   ├── events.py             # Internal event definitions
│   └── orchestrator.py       # Core coordinating loop & audio pump
├── devices/
│   ├── base.py               # Typed DeviceAgent abstract base class
│   ├── paperball.py          # Native macOS agent (safe app/URL launch, injection-proof)
│   └── error_boy.py          # Remote Linux agent (HTTP API with graceful offline fallback)
├── tools/
│   ├── base.py               # BaseTool & ToolRegistry
│   └── system_tools.py       # OpenAppTool, OpenUrlTool, SystemStatusTool
├── voice/
│   ├── audio/
│   │   ├── stream.py         # Non-blocking MicrophoneStream
│   │   └── player.py         # InterruptibleAudioPlayer with instant abort()
│   ├── wake/
│   │   └── openwakeword_provider.py # Dedicated ONNX continuous detector
│   ├── vad/
│   │   └── silero_vad.py     # Local Silero VAD provider
│   ├── stt/
│   │   └── faster_whisper_stt.py    # Local Faster-Whisper int8 provider
│   └── tts/
│       └── kokoro_tts.py     # Local Kokoro-82M human voice provider
├── tests/                    # 17 Unit & integration tests
├── pyproject.toml            # Build & package configuration
├── requirements.txt          # Frozen dependency manifest
└── main.py                   # Assistant entry point
```

---

## 🤝 Contributing

Contributions to the **Brown Open Source Project** are warmly welcomed!
See [CONTRIBUTING.md](CONTRIBUTING.md) for instructions on setting up your development environment, submitting pull requests, and adhering to our code standards.

---

## 📄 License

Distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.
