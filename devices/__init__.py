try:
    from agents.base import DeviceAgent, DeviceCommandResult
    from agents.paperball import PaperballAgent
    from agents.error_boy import ErrorBoyAgent

    __all__ = ["DeviceAgent", "DeviceCommandResult", "PaperballAgent", "ErrorBoyAgent"]
except ImportError:
    # Allow running lightweight utilities (e.g. error_boy_server) without full agent dependencies
    __all__ = []
