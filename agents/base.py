from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DeviceCommandResult(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class DeviceAgent(ABC):
    """Abstract interface for typed device control nodes.
    Provides strict typed actions. No arbitrary shell execution allowed.
    All device actions are capability-based, generic, and user-configurable.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Device canonical ID, e.g. 'host' or 'node_1'."""
        pass

    @property
    def display_name(self) -> str:
        """User-friendly display name for this device."""
        return getattr(self, "_display_name", self.name)

    @display_name.setter
    def display_name(self, value: str):
        self._display_name = value

    @property
    def operating_system(self) -> str:
        """Operating system family: 'macos', 'linux', 'windows', 'generic'."""
        return getattr(self, "_operating_system", "generic")

    @operating_system.setter
    def operating_system(self, value: str):
        self._operating_system = value

    @property
    @abstractmethod
    def is_online(self) -> bool:
        """Check if device is currently reachable."""
        pass

    @property
    def is_local(self) -> bool:
        """Whether this device is the local host running Brown."""
        return False

    @property
    def capabilities(self) -> List[str]:
        """List of supported capability identifiers."""
        return [
            "open_application",
            "close_application",
            "open_url",
            "get_system_status",
            "get_running_apps",
            "get_device_capabilities",
        ]

    @property
    def roles(self) -> List[str]:
        """Configured roles for this device, e.g. ['desktop', 'audio_io', 'local_inference']."""
        return []

    @abstractmethod
    def open_application(self, app_name: str) -> DeviceCommandResult:
        """Safely open an application on this device."""
        pass

    @abstractmethod
    def close_application(self, app_name: str) -> DeviceCommandResult:
        """Safely close an application on this device."""
        pass

    @abstractmethod
    def open_url(self, url: str) -> DeviceCommandResult:
        """Safely open a URL in the default or specified browser on this device."""
        pass

    @abstractmethod
    def get_system_status(self) -> DeviceCommandResult:
        """Get CPU/memory/status overview safely."""
        pass

    def get_device_status(self) -> DeviceCommandResult:
        """Alias for get_system_status for consistent capability naming."""
        return self.get_system_status()

    @abstractmethod
    def get_running_apps(self) -> DeviceCommandResult:
        """Safely list running user applications on this device."""
        pass

    @abstractmethod
    def get_device_capabilities(self) -> DeviceCommandResult:
        """Retrieve the typed capabilities and OS metadata supported by this device."""
        pass

    # Clipboard capabilities (Phase D)
    def get_clipboard_text(self) -> DeviceCommandResult:
        """Get clipboard text contents safely."""
        return DeviceCommandResult(success=False, message="Clipboard get is not supported on this device.")

    def set_clipboard_text(self, text: str) -> DeviceCommandResult:
        """Set clipboard text contents safely."""
        return DeviceCommandResult(success=False, message="Clipboard set is not supported on this device.")

    def clear_clipboard(self) -> DeviceCommandResult:
        """Clear clipboard contents safely."""
        return DeviceCommandResult(success=False, message="Clipboard clear is not supported on this device.")

    # File transfer capabilities (Phase E)
    def receive_file(self, filename: str, content_b64: str, target_dir: Optional[str] = None, expected_sha256: Optional[str] = None) -> DeviceCommandResult:
        """Safely receive a file transferred from another device."""
        return DeviceCommandResult(success=False, message="File transfer receive is not supported on this device.")

    def send_file(self, filename: str, source_dir: Optional[str] = None) -> DeviceCommandResult:
        """Safely send a file to another device."""
        return DeviceCommandResult(success=False, message="File transfer send is not supported on this device.")
