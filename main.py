import os
import sys
import time
import yaml
import numpy as np
from typing import Dict, Any

from core.orchestrator import BrownOrchestrator
from tools.base import ToolRegistry
from tools.system_tools import OpenAppTool, CloseAppTool, OpenUrlTool, SystemStatusTool, GetRunningAppsTool, GetCapabilitiesTool
from devices.paperball import PaperballAgent
from devices.error_boy import ErrorBoyAgent

from voice.audio.stream import MicrophoneStream
from voice.audio.player import InterruptibleAudioPlayer
from voice.wake.openwakeword_provider import OpenWakeWordProvider
from voice.wake.brown_wake_provider import BrownWakeWordProvider
from voice.vad.silero_vad import SileroVADProvider
from voice.stt.faster_whisper_stt import FasterWhisperSTT
from voice.tts.kokoro_tts import KokoroTTS


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
    paperball = PaperballAgent()
    eb_cfg = config.get("devices", {}).get("error_boy", {})
    eb_url = os.environ.get("ERROR_BOY_BASE_URL") or eb_cfg.get("base_url", "http://error-boy.local:8765")
    error_boy = ErrorBoyAgent(
        base_url=eb_url,
        timeout=eb_cfg.get("timeout", 2.0)
    )
    devices = {
        "paperball": paperball,
        "error_boy": error_boy
    }

    # 2. Tool registry
    registry = ToolRegistry()
    registry.register(OpenAppTool(devices))
    registry.register(CloseAppTool(devices))
    registry.register(OpenUrlTool(devices))
    registry.register(SystemStatusTool(devices))
    registry.register(GetRunningAppsTool(devices))
    registry.register(GetCapabilitiesTool(devices))

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

    wake_cfg = config.get("wake", {})
    provider_type = wake_cfg.get("provider", "brown")
    if provider_type == "brown":
        triggers = wake_cfg.get("trigger_phrases", None)
        wake_provider = BrownWakeWordProvider(stt_provider=stt_provider, trigger_phrases=triggers)
    else:
        wake_models = [wake_cfg.get("model_name", "alexa")]
        wake_provider = OpenWakeWordProvider(model_names=wake_models, threshold=wake_cfg.get("threshold", 0.5))

    vad_cfg = config.get("vad", {})
    vad_provider = SileroVADProvider(threshold=vad_cfg.get("threshold", 0.5))

    tts_cfg = config.get("tts", {})
    tts_provider = KokoroTTS(voice=tts_cfg.get("voice", "af_bella"))

    # 5. Orchestrator
    conv_cfg = config.get("conversation", {})
    orchestrator = BrownOrchestrator(
        audio_input=audio_in,
        audio_output=audio_out,
        wake_provider=wake_provider,
        vad_provider=vad_provider,
        stt_provider=stt_provider,
        tts_provider=tts_provider,
        tool_registry=registry,
        conversation_timeout=conv_cfg.get("timeout_seconds", 8.0),
        min_speech_duration_ms=vad_cfg.get("min_speech_duration_ms", 250),
        min_silence_duration_ms=vad_cfg.get("min_silence_duration_ms", 700),
        greeting=conv_cfg.get("greeting", "Yeah, I'm here. What can I do for you?")
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
    args = parser.parse_args()

    print("=" * 65)
    print(" 🇮🇳 Brown — Personal AI Computer Assistant (Open-Source India)")
    print("=" * 65)
    cfg = load_config(args.config)
    orchestrator = build_orchestrator(cfg)

    if not args.no_warmup:
        warmup_engine(orchestrator)

    try:
        orchestrator.start()
        print("\nBrown is actively listening. Say 'Hey Brown' or 'Brown' to activate.")
        print("Press Ctrl+C to exit.\n")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping Brown...")
        orchestrator.stop()
        print("Goodbye.")


if __name__ == "__main__":
    main()
