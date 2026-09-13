import os
import sys
import time
import yaml
import numpy as np
from typing import Dict, Any

from core.orchestrator import BrownOrchestrator
from core.events import UIEventBridge
from core.device_resolver import DeviceResolver
from core.ai.local_provider import LocalAIProvider
from core.ai.cloud_provider import CloudAIProvider
from core.ai.router import AIRouter
from core.ai.brain import BrownBrain
from tools.base import ToolRegistry
from tools.system_tools import (
    OpenAppTool,
    CloseAppTool,
    OpenUrlTool,
    SystemStatusTool,
    GetRunningAppsTool,
    GetCapabilitiesTool,
    GetLocalAIStatusTool,
    ManageLocalAITool
)
from agents.local_agent import LocalAgent
from agents.remote_agent import RemoteAgent

from voice.audio.stream import MicrophoneStream
from voice.audio.player import InterruptibleAudioPlayer
from voice.wake.openwakeword_provider import OpenWakeWordProvider
from voice.wake.brown_wake_provider import BrownWakeWordProvider
from voice.vad.silero_vad import SileroVADProvider
from voice.stt.faster_whisper_stt import FasterWhisperSTT
from voice.tts.kokoro_tts import KokoroTTS


def load_env(env_path: str = ".env"):
    """Load key-value pairs from .env into os.environ if present."""
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

load_env()


def load_config(path: str = "config/default.yaml") -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            cfg = yaml.safe_load(f) or {}

    # Merge gitignored private local overrides (config/local.yaml) if present
    local_path = "config/local.yaml"
    if os.path.exists(local_path):
        with open(local_path, "r") as f:
            local_cfg = yaml.safe_load(f) or {}
            if "devices" in local_cfg:
                cfg.setdefault("devices", {})
                for k, v in local_cfg["devices"].items():
                    if isinstance(v, dict):
                        cfg["devices"].setdefault(k, {}).update(v)
                    else:
                        cfg["devices"][k] = v

    return cfg


def build_orchestrator(config: Dict[str, Any]) -> BrownOrchestrator:
    # 1. Device agents
    local_agent = LocalAgent()
    node_cfg = config.get("devices", {}).get("remote_node", config.get("devices", {}).get("error_boy", {}))
    from core.settings import get_settings
    user_settings = get_settings()
    node_url = (
        os.environ.get("BROWN_REMOTE_URL")
        or os.environ.get("ERROR_BOY_BASE_URL")
        or user_settings.get("remoteNodeUrl")
        or user_settings.get("localAiUrl")
        or node_cfg.get("base_url", "http://10.217.30.46:8765")
    )
    remote_agent = RemoteAgent(
        base_url=node_url,
        timeout=node_cfg.get("timeout", 2.0)
    )
    devices = {
        "host": local_agent,
        "remote_node": remote_agent,
        "paperball": local_agent,
        "error_boy": remote_agent,
    }

    # 2. Tool registry
    registry = ToolRegistry()
    registry.register(OpenAppTool(devices))
    registry.register(CloseAppTool(devices))
    registry.register(OpenUrlTool(devices))
    registry.register(SystemStatusTool(devices))
    registry.register(GetRunningAppsTool(devices))
    registry.register(GetCapabilitiesTool(devices))
    registry.register(GetLocalAIStatusTool(devices))
    registry.register(ManageLocalAITool(devices))

    # 3. Audio stream & player
    audio_cfg = config.get("audio", {})
    sr = audio_cfg.get("sample_rate", 16000)
    chunk_sz = audio_cfg.get("chunk_size", 1280)
    audio_in = MicrophoneStream(sample_rate=sr, chunk_size=chunk_sz)
    audio_out = InterruptibleAudioPlayer()

    # 4. Providers
    stt_cfg = config.get("stt", {})
    stt_provider = FasterWhisperSTT(
        model_size=stt_cfg.get("model_size", "base.en"),
        device=stt_cfg.get("device", "cpu"),
        compute_type=stt_cfg.get("compute_type", "int8"),
        threads=stt_cfg.get("threads", 4)
    )

    vad_cfg = config.get("vad", {})
    vad_provider = SileroVADProvider(threshold=vad_cfg.get("threshold", 0.5))

    tts_cfg = config.get("tts", {})
    tts_provider = KokoroTTS(voice=tts_cfg.get("voice", "af_bella"))

    # 5. Device Resolver & AI Router
    devices_cfg = config.get("devices", {})
    device_resolver = DeviceResolver(devices_cfg)

    intel_cfg = config.get("intelligence", {})
    local_ai_cfg = intel_cfg.get("local_ai", {})
    cloud_ai_cfg = intel_cfg.get("cloud_ai", {})
    routing_cfg = intel_cfg.get("routing", {})

    local_provider = LocalAIProvider(
        base_url=local_ai_cfg.get("base_url", node_url),
        model=local_ai_cfg.get("model", "qwen3-vl:2b"),
        keep_warm=local_ai_cfg.get("keep_warm", True),
        idle_unload_minutes=local_ai_cfg.get("idle_unload_minutes", 15),
        device_resolver=device_resolver
    )

    cloud_provider = None
    if cloud_ai_cfg.get("enabled"):
        cloud_provider = CloudAIProvider(
            provider_name=cloud_ai_cfg.get("preferred_provider", "openai"),
            api_key=os.environ.get(cloud_ai_cfg.get("api_key_env", "OPENAI_API_KEY")),
            privacy_mode=cloud_ai_cfg.get("privacy_mode", "local_only")
        )

    ai_router = AIRouter(
        device_resolver=device_resolver,
        local_provider=local_provider,
        cloud_provider=cloud_provider,
        privacy_mode=routing_cfg.get("privacy_mode", "local_only"),
        deterministic_first=routing_cfg.get("deterministic_first", True),
        local_first=routing_cfg.get("local_first", True),
        cloud_fallback=routing_cfg.get("cloud_fallback", False),
    )

    # 6. Wake provider with calibration diagnostics
    wake_settings = config.get("wake_settings", {})
    ui_cfg = config.get("ui", {})
    event_bridge = UIEventBridge(
        host=ui_cfg.get("host", "127.0.0.1"),
        port=ui_cfg.get("port", 8766)
    )

    def _on_wake_diagnostic(diag_data):
        if event_bridge:
            event_bridge.broadcast("wake_diagnostic", diag_data)

    wake_cfg = config.get("wake", {})
    provider_type = wake_cfg.get("provider", "brown")
    if provider_type == "brown":
        triggers = wake_cfg.get("trigger_phrases", None)
        wake_provider = BrownWakeWordProvider(
            stt_provider=stt_provider,
            trigger_phrases=triggers,
            threshold=wake_settings.get("threshold", wake_cfg.get("threshold", 0.5)),
            cooldown_sec=wake_settings.get("cooldown_sec", 2.0),
            calibration_mode=wake_settings.get("calibration_mode", False),
            on_diagnostic=_on_wake_diagnostic
        )
    else:
        wake_models = [wake_cfg.get("model_name", "alexa")]
        wake_provider = OpenWakeWordProvider(model_names=wake_models, threshold=wake_cfg.get("threshold", 0.5))

    # 7. Conversational Brain (PydanticAI)
    brain_settings = {**config, **user_settings}
    brain = BrownBrain(
        device_resolver=device_resolver,
        tool_registry=registry,
        devices=devices,
        settings=brain_settings,
        event_bridge=event_bridge,
    )

    # 8. Orchestrator
    conv_cfg = config.get("conversation", {})
    orchestrator = BrownOrchestrator(
        audio_input=audio_in,
        audio_output=audio_out,
        wake_provider=wake_provider,
        vad_provider=vad_provider,
        stt_provider=stt_provider,
        tts_provider=tts_provider,
        tool_registry=registry,
        brain=brain,
        conversation_timeout=conv_cfg.get("timeout_seconds", 8.0),
        min_speech_duration_ms=vad_cfg.get("min_speech_duration_ms", 250),
        min_silence_duration_ms=vad_cfg.get("min_silence_duration_ms", 700),
        greeting=conv_cfg.get("greeting", "Yeah, I'm here. What can I do for you?"),
        event_bridge=event_bridge,
        ai_router=ai_router,
        device_resolver=device_resolver,
        auto_warm=local_ai_cfg.get("auto_warm", True),
        auto_start=local_ai_cfg.get("auto_start", True),
    )
    orchestrator.barge_in_enabled = conv_cfg.get("barge_in_enabled", True)
    orchestrator.barge_in_grace_period_sec = conv_cfg.get("barge_in_grace_period_sec", 1.2)
    orchestrator.barge_in_min_frames = conv_cfg.get("barge_in_min_frames", 3)
    return orchestrator



def warmup_engine(orchestrator: BrownOrchestrator):
    """Preloads neural models (Wake, VAD, STT, TTS) into memory for sub-second turn latency."""
    print("[Brown] Pre-warming models for zero-lag performance...")
    t0 = time.time()
    try:
        orchestrator.wake_provider.start()
        orchestrator.vad_provider.is_speech(np.zeros(512, dtype=np.float32))
        orchestrator.tts_provider.synthesize("Ready.")
        orchestrator.stt_provider.transcribe(np.zeros(16000, dtype=np.float32))
        print(f"[Brown] Engine warmed up in {time.time() - t0:.2f}s! All models hot in RAM.")
    except Exception as e:
        print(f"[Brown] Warmup warning: {e}")


def main():
    import argparse
    import numpy as np

    parser = argparse.ArgumentParser(description="Brown — Voice-First AI Computer Assistant")
    parser.add_argument("--config", default="config/default.yaml", help="Path to config file")
    parser.add_argument("--no-warmup", action="store_true", help="Skip model pre-warming")
    parser.add_argument("--text", action="store_true", help="Run in interactive text/chat mode without microphone")
    args = parser.parse_args()

    print("=" * 65)
    print(" 🇮🇳 Brown — Personal AI Computer Assistant (Open-Source India)")
    print("=" * 65)
    cfg = load_config(args.config)
    orchestrator = build_orchestrator(cfg)

    if args.text:
        print("\n[Brown] Interactive Agent Mode (Agent-Driven Testing)")
        print("Type any question or command for Brown (e.g. 'is the local llm running', 'can you run it on secondary machine')")
        print("Type 'exit' to quit.\n")
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    print("Goodbye.")
                    break
                resp = orchestrator._process_command(user_input)
                print(f"Brown: {resp}")
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye.")
                break
        return

    if not args.no_warmup:
        warmup_engine(orchestrator)

    try:
        orchestrator.start()
        print("\nBrown is actively listening. Say 'Hey Brown' or 'Brown' to activate.")
        print("Press Ctrl+C to exit.\n")
        while True:
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit):
        print("\nStopping Brown...")
        try:
            orchestrator.stop()
        except Exception:
            pass
        print("Goodbye.")
        sys.exit(0)


if __name__ == "__main__":
    main()

