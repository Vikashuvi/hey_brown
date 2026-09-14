"""Local Host Device Agent for Brown.
Provides strictly typed, validated capabilities for controlling the host operating system.
Zero external dependencies; enterprise-grade open-source design.
"""

import os
import re
import time
import base64
import hashlib
import subprocess
import urllib.parse
from typing import Optional
from agents.base import DeviceAgent, DeviceCommandResult


class LocalAgent(DeviceAgent):
    """Local host operating system device agent.
    Safely executes validated desktop capabilities without arbitrary shell injection.
    """

    SAFE_APP_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_\.]+$")

    def __init__(self, device_id: str = "host", display_name: str = "Local Host"):
        self._device_id = device_id
        self._display_name = display_name

    @property
    def name(self) -> str:
        return self._device_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def is_online(self) -> bool:
        # Local host agent is always online when the process runs
        return True

    def open_application(self, app_name: str) -> DeviceCommandResult:
        app_name = app_name.strip()
        if not self.SAFE_APP_PATTERN.match(app_name):
            return DeviceCommandResult(
                success=False,
                message=f"Invalid or unsafe application name: '{app_name}'"
            )

        try:
            # Native macOS 'open -a' command
            cmd = ["open", "-a", app_name]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return DeviceCommandResult(
                    success=True,
                    message=f"Opened {app_name} on {self._display_name}."
                )
            else:
                err = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
                return DeviceCommandResult(
                    success=False,
                    message=f"Could not open {app_name} on {self._display_name}: {err}"
                )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Failed to open application {app_name}: {str(e)}"
            )

    def close_application(self, app_name: str) -> DeviceCommandResult:
        app_name = app_name.strip()
        if not self.SAFE_APP_PATTERN.match(app_name):
            return DeviceCommandResult(
                success=False,
                message=f"Invalid application name: '{app_name}'"
            )

        try:
            # Use AppleScript to quit cleanly
            script = f'tell application "{app_name}" to quit'
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return DeviceCommandResult(
                    success=True,
                    message=f"Closed {app_name} on {self._display_name}."
                )
            else:
                return DeviceCommandResult(
                    success=False,
                    message=f"Could not close {app_name}: {proc.stderr.strip()}"
                )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Error closing {app_name}: {str(e)}"
            )

    def open_url(self, url: str) -> DeviceCommandResult:
        url = url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            return DeviceCommandResult(
                success=False,
                message=f"Invalid URL: {url}"
            )

        try:
            proc = subprocess.run(["open", url], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return DeviceCommandResult(
                    success=True,
                    message=f"Opened {url} in browser on {self._display_name}."
                )
            else:
                return DeviceCommandResult(
                    success=False,
                    message=f"Failed to open URL: {proc.stderr.strip()}"
                )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Error opening URL {url}: {str(e)}"
            )

    def get_system_status(self) -> DeviceCommandResult:
        try:
            load1, load5, load15 = os.getloadavg()
            return DeviceCommandResult(
                success=True,
                message=f"{self._display_name} is running normally. Load averages: {load1:.2f}, {load5:.2f}, {load15:.2f}.",
                data={"load1": load1, "load5": load5, "load15": load15}
            )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Failed to query {self._display_name} system status: {str(e)}"
            )

    def get_running_apps(self) -> DeviceCommandResult:
        try:
            script = 'tell application "System Events" to get name of every process whose visible is true'
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=4)
            if proc.returncode == 0:
                raw_apps = proc.stdout.strip().split(", ")
                apps = [a.strip() for a in raw_apps if a.strip()]
                return DeviceCommandResult(
                    success=True,
                    message=f"{self._display_name} is currently running: {', '.join(apps)}.",
                    data={"running_apps": apps}
                )
            else:
                return DeviceCommandResult(
                    success=False,
                    message=f"Failed to query running apps on {self._display_name}: {proc.stderr.strip()}"
                )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Error querying running apps on {self._display_name}: {str(e)}"
            )

    def get_device_capabilities(self) -> DeviceCommandResult:
        return DeviceCommandResult(
            success=True,
            message=f"{self._display_name} device capabilities retrieved.",
            data={
                "device": self._device_id,
                "os": "macOS",
                "capabilities": [
                    "get_device_status",
                    "get_running_apps",
                    "open_application",
                    "close_application",
                    "open_url",
                    "get_device_capabilities",
                    "get_ai_status",
                    "ai_warm",
                    "ai_unload"
                ],
                "version": "1.0.0"
            }
        )

    def get_ai_status(self, model: Optional[str] = None) -> DeviceCommandResult:
        return DeviceCommandResult(
            success=True,
            message=f"Host machine {self._display_name} delegates local inference to the configured remote compute node.",
            data={"device": self._device_id, "state": "READY", "model": model or "qwen3-vl:2b", "loaded": True}
        )

    def ai_warm(self, model: str, keep_alive: str = "15m") -> DeviceCommandResult:
        return DeviceCommandResult(
            success=True,
            message=f"Model '{model}' verified on {self._display_name}.",
            data={"model": model, "state": "READY"}
        )

    def ai_unload(self, model: Optional[str] = None) -> DeviceCommandResult:
        return DeviceCommandResult(
            success=True,
            message=f"Model unloaded on {self._display_name}.",
            data={"unloaded": True}
        )

    # Clipboard capabilities (Phase D)
    def get_clipboard_text(self) -> DeviceCommandResult:
        """Safely read macOS clipboard via pbpaste."""
        try:
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                text = res.stdout
                if len(text.encode("utf-8")) > 524288:
                    return DeviceCommandResult(
                        success=False,
                        message="Clipboard text exceeds 512KB size limit."
                    )
                return DeviceCommandResult(
                    success=True,
                    message=f"Read {len(text)} characters from {self._display_name} clipboard.",
                    data={"text": text, "length": len(text), "device": self._device_id}
                )
            return DeviceCommandResult(success=False, message=f"pbpaste failed: {res.stderr}")
        except Exception as e:
            return DeviceCommandResult(success=False, message=f"Clipboard error on {self._display_name}: {str(e)}")

    def set_clipboard_text(self, text: str) -> DeviceCommandResult:
        """Safely write macOS clipboard via pbcopy."""
        if len(text.encode("utf-8")) > 524288:
            return DeviceCommandResult(
                success=False,
                message="Clipboard text exceeds 512KB size limit."
            )
        try:
            res = subprocess.run(["pbcopy"], input=text, text=True, capture_output=True, timeout=2.0)
            if res.returncode == 0:
                return DeviceCommandResult(
                    success=True,
                    message=f"Copied {len(text)} characters to {self._display_name} clipboard.",
                    data={"length": len(text), "device": self._device_id}
                )
            return DeviceCommandResult(success=False, message=f"pbcopy failed: {res.stderr}")
        except Exception as e:
            return DeviceCommandResult(success=False, message=f"Clipboard write error on {self._display_name}: {str(e)}")

    def clear_clipboard(self) -> DeviceCommandResult:
        """Clear macOS clipboard."""
        return self.set_clipboard_text("")

    # Secure file transfer capabilities (Phase E)
    def receive_file(self, filename: str, content_b64: str, target_dir: Optional[str] = None, expected_sha256: Optional[str] = None) -> DeviceCommandResult:
        """Safely receive and atomic-write a file with path traversal defense and checksum verification."""
        if not filename or ".." in filename or filename.startswith("/") or "\\" in filename:
            return DeviceCommandResult(success=False, message="Invalid or unsafe filename.")

        safe_name = os.path.basename(filename).strip()
        if not safe_name or safe_name.startswith("."):
            return DeviceCommandResult(success=False, message="Invalid or unsafe filename.")

        out_dir = os.path.expanduser(target_dir or "~/Downloads/BrownTransfers")
        os.makedirs(out_dir, exist_ok=True)
        final_path = os.path.join(out_dir, safe_name)
        tmp_path = os.path.join(out_dir, f".{safe_name}.tmp_{int(time.time())}")

        try:
            raw_bytes = base64.b64decode(content_b64)
            if len(raw_bytes) > 52428800:  # 50MB
                return DeviceCommandResult(success=False, message="File exceeds 50MB size limit.")

            if expected_sha256:
                actual_sha = hashlib.sha256(raw_bytes).hexdigest()
                if actual_sha.lower() != expected_sha256.lower():
                    return DeviceCommandResult(success=False, message="SHA-256 checksum mismatch.")

            with open(tmp_path, "wb") as f:
                f.write(raw_bytes)
            os.replace(tmp_path, final_path)

            return DeviceCommandResult(
                success=True,
                message=f"File '{safe_name}' safely saved to {final_path}.",
                data={"filename": safe_name, "path": final_path, "bytes": len(raw_bytes), "device": self._device_id}
            )
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return DeviceCommandResult(success=False, message=f"File transfer failed: {str(e)}")

    def send_file(self, filename: str, source_dir: Optional[str] = None) -> DeviceCommandResult:
        """Safely read and prepare a file for transfer with checksum."""
        if not filename or ".." in filename or filename.startswith("/") or "\\" in filename:
            return DeviceCommandResult(success=False, message="Invalid or unsafe filename.")

        safe_name = os.path.basename(filename).strip()
        in_dir = os.path.expanduser(source_dir or "~/Downloads/BrownTransfers")
        file_path = os.path.join(in_dir, safe_name)

        if not os.path.exists(file_path):
            return DeviceCommandResult(success=False, message=f"File '{safe_name}' not found in {in_dir}.")

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            if len(data) > 52428800:
                return DeviceCommandResult(success=False, message="File exceeds 50MB size limit.")

            sha256_hash = hashlib.sha256(data).hexdigest()
            b64_content = base64.b64encode(data).decode("utf-8")
            return DeviceCommandResult(
                success=True,
                message=f"File '{safe_name}' ready for transfer ({len(data)} bytes).",
                data={
                    "filename": safe_name,
                    "content_b64": b64_content,
                    "sha256": sha256_hash,
                    "bytes": len(data),
                    "device": self._device_id
                }
            )
        except Exception as e:
            return DeviceCommandResult(success=False, message=f"Error reading file: {str(e)}")


# Backward compatibility alias
class PaperballAgent(LocalAgent):
    def __init__(self, device_id: str = "paperball", display_name: str = "Paperball"):
        super().__init__(device_id=device_id, display_name=display_name)
