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
