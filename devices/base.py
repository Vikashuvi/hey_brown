from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DeviceCommandResult(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class DeviceAgent(ABC):
    """Abstract interface for typed device control nodes (Paperball, Error Boy).
    Provides strict typed actions. No arbitrary shell execution allowed.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Device name, e.g. 'paperball' or 'error_boy'."""
        pass

    @property
    @abstractmethod
    def is_online(self) -> bool:
        """Check if device is currently reachable."""
        pass

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
