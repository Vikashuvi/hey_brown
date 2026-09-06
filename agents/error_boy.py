import requests
from typing import Optional, Dict, Any
from agents.base import DeviceAgent, DeviceCommandResult


class ErrorBoyAgent(DeviceAgent):
    """Remote Linux device agent endpoint for Error Boy (Arch Linux).
    Communicates via authenticated HTTP / JSON API.
    Handles offline state gracefully so Paperball never blocks or fails.
    """

    def __init__(self, base_url: str = "http://error-boy.local:8765", auth_token: Optional[str] = None, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "error_boy"

    @property
    def is_online(self) -> bool:
        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            resp = requests.get(f"{self.base_url}/health", headers=headers, timeout=self.timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def _send_command(self, endpoint: str, payload: Dict[str, Any]) -> DeviceCommandResult:
        try:
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            resp = requests.post(
                f"{self.base_url}/{endpoint}",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            data = resp.json()
            return DeviceCommandResult(
                success=data.get("success", False),
                message=data.get("message", "Error Boy executed command."),
                data=data.get("data")
            )
        except requests.exceptions.ConnectionError:
            return DeviceCommandResult(
                success=False,
                message="Error Boy is currently offline or unreachable on the network."
            )
        except requests.exceptions.Timeout:
            return DeviceCommandResult(
                success=False,
                message="Request to Error Boy timed out."
            )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Communication error with Error Boy: {str(e)}"
            )

    def open_application(self, app_name: str) -> DeviceCommandResult:
        return self._send_command("apps/open", {"application": app_name})

    def close_application(self, app_name: str) -> DeviceCommandResult:
        return self._send_command("apps/close", {"application": app_name})

    def open_url(self, url: str) -> DeviceCommandResult:
        return self._send_command("browser/open", {"url": url})

    def get_system_status(self) -> DeviceCommandResult:
        return self._send_command("system/status", {})
