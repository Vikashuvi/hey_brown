try:
    from agents.base import DeviceAgent, DeviceCommandResult
    from agents.local_agent import LocalAgent, PaperballAgent
    from agents.remote_agent import RemoteAgent, ErrorBoyAgent

    __all__ = [
        "DeviceAgent",
        "DeviceCommandResult",
        "LocalAgent",
        "RemoteAgent",
        "PaperballAgent",
        "ErrorBoyAgent"
    ]
except ImportError:
    __all__ = []
