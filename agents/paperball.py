import os
import re
import subprocess
import urllib.parse
from typing import Optional
from devices.base import DeviceAgent, DeviceCommandResult


class PaperballAgent(DeviceAgent):
    """Local macOS device agent for Paperball.
    Provides strictly typed, validated capabilities.
    """

    SAFE_APP_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_\.]+$")

    @property
    def name(self) -> str:
        return "paperball"

    @property
    def is_online(self) -> bool:
        # Paperball is the local machine, so it is always online if Brown is running
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
                    message=f"Opened {app_name} on Paperball."
                )
            else:
                err = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
                return DeviceCommandResult(
                    success=False,
                    message=f"Could not open {app_name} on Paperball: {err}"
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
                    message=f"Closed {app_name} on Paperball."
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
                    message=f"Opened {url} in browser on Paperball."
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
            # Load averages
            load1, load5, load15 = os.getloadavg()
            return DeviceCommandResult(
                success=True,
                message=f"Paperball is running normally. Load averages: {load1:.2f}, {load5:.2f}, {load15:.2f}.",
                data={"load1": load1, "load5": load5, "load15": load15}
            )
        except Exception as e:
            return DeviceCommandResult(
                success=False,
                message=f"Failed to query Paperball system status: {str(e)}"
            )
