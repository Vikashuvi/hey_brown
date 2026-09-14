"""Remote Node Device Agent for Brown.
Communicates strictly via authenticated HTTP / JSON REST API with remote worker/inference nodes.
Provides typed capabilities with short, bounded timeouts so Brown never freezes when a remote node is offline.
"""

import requests
from typing import Optional, Dict, Any
from agents.base import DeviceAgent, DeviceCommandResult


class RemoteAgent(DeviceAgent):
    """Remote accelerator or worker node device agent client.
    Issues typed capability requests over HTTP REST API to the node daemon.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        device_id: str = "remote_node",
        display_name: str = "Remote Node",
        auth_token: Optional[str] = None,
        timeout: float = 2.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.display_name = display_name
        self.auth_token = auth_token
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self.device_id

    @property
    def is_online(self) -> bool:
        """Check whether the remote node is reachable on the network."""
        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            resp = requests.get(f"{self.base_url}/health", headers=headers, timeout=self.timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def _send_command(self, endpoint: str, payload: Optional[Dict[str, Any]] = None, method: str = "POST", timeout: Optional[float] = None) -> DeviceCommandResult:
        """Issue an authenticated, timeout-bounded HTTP request to the remote node."""
        req_timeout = timeout if timeout is not None else self.timeout
        try:
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=req_timeout)
            else:
                resp = requests.post(url, json=payload or {}, headers=headers, timeout=req_timeout)

            try:
                data = resp.json()
            except Exception:
                return DeviceCommandResult(
                    success=resp.status_code == 200,
                    message=f"Received status {resp.status_code} from {self.display_name}."
                )

            return DeviceCommandResult(
                success=data.get("success", False),
                message=data.get("message", f"{self.display_name} executed command."),
                data=data.get("data")
            )
        except requests.exceptions.ConnectionError:
            return DeviceCommandResult(
                success=False,
                message=f"{self.display_name} is currently offline or unreachable on the network."
            )
        except requests.exceptions.Timeout:
            return DeviceCommandResult(
                success=False,
                message=f"Request to {self.display_name} timed out."
            )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Communication error with {self.display_name}: {str(e)}"
            )

    # 1. Device Status
    def get_system_status(self) -> DeviceCommandResult:
        return self._send_command("system/status", method="GET")

    def get_device_status(self) -> DeviceCommandResult:
        return self.get_system_status()

    # 2. Running Applications
    def get_running_apps(self) -> DeviceCommandResult:
        return self._send_command("apps/running", method="GET")

    # 3. Open Application
    def open_application(self, app_name: str) -> DeviceCommandResult:
        return self._send_command("apps/open", {"application": app_name}, method="POST")

    # 4. Close Application
    def close_application(self, app_name: str) -> DeviceCommandResult:
        return self._send_command("apps/close", {"application": app_name}, method="POST")

    # 5. Open URL
    def open_url(self, url: str) -> DeviceCommandResult:
        return self._send_command("browser/open", {"url": url}, method="POST")

    # 6. Capabilities Discovery
    def get_device_capabilities(self) -> DeviceCommandResult:
        return self._send_command("capabilities", method="GET")

    # 7. AI Health Status & Telemetry
    def get_ai_status(self, model: Optional[str] = None) -> DeviceCommandResult:
        endpoint = f"ai/status?model={model}" if model else "ai/status"
        return self._send_command(endpoint, method="GET", timeout=5.0)

    # 8. Available Models Discovery
    def get_ai_models(self) -> DeviceCommandResult:
        return self._send_command("ai/models", method="GET", timeout=10.0)

    # 9. Preload / Warm Model
    def ai_warm(self, model: str, keep_alive: str = "15m") -> DeviceCommandResult:
        return self._send_command("ai/warm", {"model": model, "keep_alive": keep_alive}, method="POST", timeout=35.0)

    # 10. AI Chat / Inference
    def ai_chat(self, messages: list, model: str = "qwen3-vl:2b", temperature: float = 0.2, max_tokens: int = 512, tools: Optional[list] = None) -> DeviceCommandResult:
        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools or []
        }
        return self._send_command("ai/chat", payload, method="POST", timeout=60.0)

    # 11. Unload Model from Memory
    def ai_unload(self, model: Optional[str] = None) -> DeviceCommandResult:
        payload = {"model": model} if model else {}
        return self._send_command("ai/unload", payload, method="POST", timeout=10.0)

    # 12. Clipboard Operations (Phase D)
    def get_clipboard_text(self) -> DeviceCommandResult:
        return self._send_command("clipboard/get", method="GET", timeout=2.0)

    def set_clipboard_text(self, text: str) -> DeviceCommandResult:
        if len(text.encode("utf-8")) > 524288:
            return DeviceCommandResult(success=False, message="Clipboard text exceeds 512KB limit.")
        return self._send_command("clipboard/set", {"text": text}, method="POST", timeout=2.0)

    def clear_clipboard(self) -> DeviceCommandResult:
        return self._send_command("clipboard/clear", method="POST", timeout=2.0)

    # 13. File Transfer Operations (Phase E)
    def receive_file(self, filename: str, content_b64: str, target_dir: Optional[str] = None, expected_sha256: Optional[str] = None) -> DeviceCommandResult:
        payload = {
            "filename": filename,
            "content_b64": content_b64,
            "target_dir": target_dir,
            "sha256": expected_sha256
        }
        return self._send_command("files/upload", payload, method="POST", timeout=15.0)

    def send_file(self, filename: str, source_dir: Optional[str] = None) -> DeviceCommandResult:
        payload = {"filename": filename, "source_dir": source_dir}
        return self._send_command("files/download", payload, method="POST", timeout=15.0)


# Backward compatibility alias
class ErrorBoyAgent(RemoteAgent):
    def __init__(
        self,
        base_url: str = "http://error-boy.local:8765",
        timeout: float = 2.0,
        auth_token: Optional[str] = None,
        device_id: str = "error_boy"
    ):
        super().__init__(base_url=base_url, timeout=timeout, auth_token=auth_token, device_id=device_id)
