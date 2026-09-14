from typing import Dict, Any, Optional
from tools.base import BaseTool, ToolResult
from devices.base import DeviceAgent


class OpenAppTool(BaseTool):
    """Tool to open an application on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return "Safely opens an application on a target device ('paperball' or 'error_boy')."

    def execute(self, app_name: str, device: str = "paperball", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(
                success=False,
                message=f"Unknown device '{device}'. Available: {list(self.devices.keys())}"
            )

        cmd_res = target_device.open_application(app_name)
        return ToolResult(
            success=cmd_res.success,
            message=cmd_res.message,
            data=cmd_res.data
        )


class CloseAppTool(BaseTool):
    """Tool to close an application on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "close_application"

    @property
    def description(self) -> str:
        return "Safely closes an application on a target device ('paperball' or 'error_boy')."

    def execute(self, app_name: str, device: str = "paperball", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(
                success=False,
                message=f"Unknown device '{device}'."
            )

        cmd_res = target_device.close_application(app_name)
        return ToolResult(
            success=cmd_res.success,
            message=cmd_res.message,
            data=cmd_res.data
        )


class OpenUrlTool(BaseTool):
    """Tool to open a web page/URL on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "open_url"

    @property
    def description(self) -> str:
        return "Safely opens a URL in the browser on a target device."

    def execute(self, url: str, device: str = "paperball", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(
                success=False,
                message=f"Unknown device '{device}'."
            )

        cmd_res = target_device.open_url(url)
        return ToolResult(
            success=cmd_res.success,
            message=cmd_res.message,
            data=cmd_res.data
        )


class SystemStatusTool(BaseTool):
    """Tool to get system status/health overview on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "get_system_status"

    @property
    def description(self) -> str:
        return "Retrieves CPU and health status from target device."

    def execute(self, device: str = "paperball", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(
                success=False,
                message=f"Unknown device '{device}'."
            )

        cmd_res = target_device.get_system_status()
        return ToolResult(
            success=cmd_res.success,
            message=cmd_res.message,
            data=cmd_res.data
        )


class GetRunningAppsTool(BaseTool):
    """Tool to list running applications on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "get_running_apps"

    @property
    def description(self) -> str:
        return "Safely retrieves list of running applications from target device."

    def execute(self, device: str = "paperball", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(
                success=False,
                message=f"Unknown device '{device}'."
            )

        cmd_res = target_device.get_running_apps()
        return ToolResult(
            success=cmd_res.success,
            message=cmd_res.message,
            data=cmd_res.data
        )


class GetCapabilitiesTool(BaseTool):
    """Tool to query typed capabilities supported by a target device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "get_device_capabilities"

    @property
    def description(self) -> str:
        return "Retrieves the list of supported typed capabilities from target device."

    def execute(self, device: str = "paperball", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(
                success=False,
                message=f"Unknown device '{device}'."
            )

        cmd_res = target_device.get_device_capabilities()
        return ToolResult(
            success=cmd_res.success,
            message=cmd_res.message,
            data=cmd_res.data
        )


class GetLocalAIStatusTool(BaseTool):
    """Tool to check if the local AI model / LLM is running on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "get_local_ai_status"

    @property
    def description(self) -> str:
        return "Checks whether the local AI model is running and loaded in memory on the target device."

    def execute(self, device: str = "remote_node", model: str = "qwen3-vl:2b", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower()) or self.devices.get("remote_node") or self.devices.get("error_boy")
        if not target_device:
            return ToolResult(success=False, message=f"No device configured for '{device}'.")

        res = target_device.get_ai_status(model=model)
        if not res.success:
            return ToolResult(
                success=False,
                message=f"Could not reach the local AI service on {target_device.display_name}."
            )

        data = res.data or {}
        state = data.get("state", "UNKNOWN")
        loaded = data.get("loaded", False)
        active_model = data.get("active_model") or data.get("model", model)

        if state == "READY" and loaded:
            msg = f"Yes, the local model '{active_model}' is running and loaded in memory on {target_device.display_name}."
        elif state == "READY":
            msg = f"The local AI runtime is online on {target_device.display_name}, but '{active_model}' is currently in standby. Say 'run it on {target_device.display_name}' to load it."
        elif state in ("STARTING", "MODEL_LOADING"):
            msg = f"The local model '{active_model}' is currently loading into memory on {target_device.display_name}."
        elif state == "RESOURCE_LIMITED":
            msg = f"The local AI service on {target_device.display_name} is constrained on memory."
        elif state == "OLLAMA_UNAVAILABLE":
            msg = f"The local AI runtime on {target_device.display_name} is currently offline."
        else:
            msg = f"Local AI state on {target_device.display_name} is {state}."

        return ToolResult(success=True, message=msg, data=data)


class ManageLocalAITool(BaseTool):
    """Tool to warm, start, or unload the local AI model on a designated device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "manage_local_ai"

    @property
    def description(self) -> str:
        return "Starts, warms, or unloads the local AI model on the designated device."

    def execute(self, action: str = "warm", device: str = "remote_node", model: str = "qwen3-vl:2b", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower()) or self.devices.get("remote_node") or self.devices.get("error_boy")
        if not target_device:
            return ToolResult(success=False, message=f"No device configured for '{device}'.")

        if action in ("warm", "start", "run", "load"):
            res = target_device.ai_warm(model=model)
            if res.success:
                return ToolResult(
                    success=True,
                    message=f"I've started '{model}' on {target_device.display_name}. It is now warmed in memory and ready.",
                    data=res.data
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Could not start '{model}' on {target_device.display_name}: {res.message}",
                    data=res.data
                )
        elif action in ("unload", "stop"):
            res = target_device.ai_unload(model=model)
            return ToolResult(
                success=True,
                message=f"Unloaded '{model}' from memory on {target_device.display_name}.",
                data=res.data
            )
        return ToolResult(success=False, message=f"Unknown action '{action}'.")


class GetClipboardTool(BaseTool):
    """Tool to read the clipboard from a target device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "get_clipboard"

    @property
    def description(self) -> str:
        return "Reads text from the clipboard of a target device."

    def execute(self, device: str = "local", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(success=False, message=f"Device '{device}' not found.")
        res = target_device.get_clipboard_text()
        return ToolResult(success=res.success, message=res.message, data=res.data)


class SetClipboardTool(BaseTool):
    """Tool to write text to the clipboard of a target device."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "set_clipboard"

    @property
    def description(self) -> str:
        return "Sets text into the clipboard of a target device."

    def execute(self, text: str, device: str = "local", **kwargs) -> ToolResult:
        target_device = self.devices.get(device.lower())
        if not target_device:
            return ToolResult(success=False, message=f"Device '{device}' not found.")
        res = target_device.set_clipboard_text(text)
        return ToolResult(success=res.success, message=res.message, data=res.data)


class SyncClipboardTool(BaseTool):
    """Tool to copy clipboard contents from one device to another."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "sync_clipboard"

    @property
    def description(self) -> str:
        return "Copies clipboard text from a source device to a target device."

    def execute(self, from_device: str, to_device: str, **kwargs) -> ToolResult:
        src = self.devices.get(from_device.lower())
        dst = self.devices.get(to_device.lower())
        if not src:
            return ToolResult(success=False, message=f"Source device '{from_device}' not found.")
        if not dst:
            return ToolResult(success=False, message=f"Target device '{to_device}' not found.")

        read_res = src.get_clipboard_text()
        if not read_res.success:
            return ToolResult(success=False, message=f"Failed to read from {src.display_name}: {read_res.message}")

        text = (read_res.data or {}).get("text", "")
        write_res = dst.set_clipboard_text(text)
        if not write_res.success:
            return ToolResult(success=False, message=f"Failed to write to {dst.display_name}: {write_res.message}")

        return ToolResult(
            success=True,
            message=f"Synchronized {len(text)} characters from {src.display_name} to {dst.display_name}.",
            data={"from_device": from_device, "to_device": to_device, "length": len(text)}
        )


class TransferFileTool(BaseTool):
    """Tool to safely transfer a file between two devices with checksum verification."""

    def __init__(self, devices: Dict[str, DeviceAgent]):
        self.devices = devices

    @property
    def name(self) -> str:
        return "transfer_file"

    @property
    def description(self) -> str:
        return "Safely transfers a file from a source device to a target destination device."

    def execute(self, filename: str, from_device: str, to_device: str, target_dir: Optional[str] = None, source_dir: Optional[str] = None, **kwargs) -> ToolResult:
        src = self.devices.get(from_device.lower())
        dst = self.devices.get(to_device.lower())
        if not src:
            return ToolResult(success=False, message=f"Source device '{from_device}' not found.")
        if not dst:
            return ToolResult(success=False, message=f"Target device '{to_device}' not found.")

        # Read from source
        send_res = src.send_file(filename=filename, source_dir=source_dir)
        if not send_res.success:
            return ToolResult(success=False, message=f"Could not read '{filename}' from {src.display_name}: {send_res.message}")

        data = send_res.data or {}
        b64 = data.get("content_b64", "")
        sha256 = data.get("sha256")

        # Write to destination
        recv_res = dst.receive_file(filename=filename, content_b64=b64, target_dir=target_dir, expected_sha256=sha256)
        if not recv_res.success:
            return ToolResult(success=False, message=f"Could not save '{filename}' on {dst.display_name}: {recv_res.message}")

        return ToolResult(
            success=True,
            message=f"Transferred '{filename}' from {src.display_name} to {dst.display_name} ({data.get('bytes', 0)} bytes).",
            data={
                "filename": filename,
                "from_device": from_device,
                "to_device": to_device,
                "bytes": data.get("bytes", 0),
                "sha256": sha256
            }
        )
