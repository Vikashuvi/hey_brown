"""Dynamic Device Resolution and Registry System for Brown.
Resolves user device mentions, roles, and configured aliases to canonical device IDs.
Supports N arbitrary devices with user-configurable capabilities, operating systems, and roles.
Zero hardcoded machine identities in logic.
"""

from typing import Dict, Any, List, Optional
import re
from pydantic import BaseModel, Field


class DeviceRecord(BaseModel):
    """Structured descriptor for a registered computer/device."""
    id: str
    display_name: str
    aliases: List[str] = Field(default_factory=list)
    operating_system: str = "generic"  # "macos", "linux", "windows", "generic"
    is_local: bool = False
    connection_url: Optional[str] = None
    auth_token: Optional[str] = None
    capabilities: List[str] = Field(default_factory=lambda: [
        "desktop_control", "get_status", "open_application", "close_application",
        "open_url", "get_running_apps", "get_device_capabilities", "clipboard", "file_transfer"
    ])
    roles: List[str] = Field(default_factory=list)
    is_online: bool = True


DEFAULT_DEVICES_CONFIG: Dict[str, Any] = {
    "paperball": {
        "id": "paperball",
        "display_name": "Paperball",
        "is_local": True,
        "operating_system": "macos",
        "capabilities": [
            "desktop_control", "get_status", "open_application", "close_application",
            "open_url", "get_running_apps", "get_device_capabilities", "clipboard", "file_transfer"
        ],
        "roles": ["primary_host", "audio_io", "desktop"],
        "aliases": [
            "paperball", "mac", "macbook", "laptop", "local", "locally", "here",
            "this machine", "this computer", "mac os", "macos", "host", "current device"
        ],
    },
    "error_boy": {
        "id": "error_boy",
        "display_name": "Error Boy",
        "is_local": False,
        "operating_system": "linux",
        "connection_url": "http://error-boy.local:8765",
        "capabilities": [
            "desktop_control", "get_status", "open_application", "close_application",
            "open_url", "get_running_apps", "get_device_capabilities", "local_llm",
            "clipboard", "file_transfer"
        ],
        "roles": ["inference_node", "secondary_worker"],
        "aliases": [
            "error boy", "error_boy", "error", "linux laptop", "linux machine",
            "linux", "secondary laptop", "secondary machine", "secondary", "other laptop",
            "other machine", "other computer", "arch linux", "arch", "victus", "pc", "forge",
            "remote node", "remote_node", "node", "remote"
        ],
    },
}


class DeviceResolver:
    """Dynamically manages registered devices and resolves freeform mentions to canonical device IDs."""

    def __init__(self, devices_config: Optional[Dict[str, Any]] = None):
        self._devices: Dict[str, DeviceRecord] = {}
        self._alias_map: Dict[str, str] = {}
        self._default_local_device: str = "paperball"
        self._default_remote_device: str = "error_boy"
        cfg = devices_config if devices_config is not None else DEFAULT_DEVICES_CONFIG
        self.update_config(cfg)

    def update_config(self, devices_config: Dict[str, Any]):
        """Load or update device definitions and alias mappings from configuration."""
        self._devices = {}
        self._alias_map = {}
        local_found = False
        remote_found = False

        for dev_id, dev_data in devices_config.items():
            if isinstance(dev_data, DeviceRecord):
                rec = dev_data
            elif isinstance(dev_data, dict):
                canonical_id = dev_data.get("id", dev_id)
                rec = DeviceRecord(
                    id=canonical_id,
                    display_name=dev_data.get("display_name", canonical_id),
                    aliases=dev_data.get("aliases", []),
                    operating_system=dev_data.get("operating_system", "generic"),
                    is_local=dev_data.get("is_local", False),
                    connection_url=dev_data.get("connection_url"),
                    auth_token=dev_data.get("auth_token"),
                    capabilities=dev_data.get("capabilities", [
                        "desktop_control", "get_status", "open_application", "close_application",
                        "open_url", "get_running_apps", "get_device_capabilities"
                    ]),
                    roles=dev_data.get("roles", []),
                    is_online=dev_data.get("is_online", True)
                )
            else:
                continue

            self._devices[rec.id] = rec

            if rec.is_local:
                if not local_found:
                    self._default_local_device = rec.id
                    local_found = True
            else:
                if not remote_found:
                    self._default_remote_device = rec.id
                    remote_found = True

            # Map canonical ID itself and display name
            self._alias_map[rec.id.lower()] = rec.id
            self._alias_map[rec.display_name.lower()] = rec.id

            # Map all declared aliases
            for alias in rec.aliases:
                self._alias_map[alias.lower().strip()] = rec.id

        # If no local device was explicitly flagged, designate the first registered device
        if self._devices and self._default_local_device not in self._devices:
            self._default_local_device = next(iter(self._devices.keys()))

    @property
    def registered_devices(self) -> List[str]:
        return list(self._devices.keys())

    @property
    def default_local_device(self) -> str:
        return self._default_local_device

    @property
    def default_remote_device(self) -> str:
        return self._default_remote_device

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        """Retrieve the structured DeviceRecord for a canonical device ID."""
        return self._devices.get(device_id)

    def get_all_devices(self) -> List[DeviceRecord]:
        """Return all registered device records."""
        return list(self._devices.values())

    def get_display_name(self, device_id: str) -> str:
        dev = self._devices.get(device_id)
        if dev:
            return dev.display_name
        return device_id

    def find_devices_by_capability(self, capability: str) -> List[str]:
        """Return IDs of all devices that advertise the requested capability."""
        matches = []
        for dev_id, dev in self._devices.items():
            if capability.lower() in [c.lower() for c in dev.capabilities]:
                matches.append(dev_id)
        return matches

    def find_devices_by_role(self, role: str) -> List[str]:
        """Return IDs of all devices assigned to a specific role."""
        matches = []
        for dev_id, dev in self._devices.items():
            if role.lower() in [r.lower() for r in dev.roles]:
                matches.append(dev_id)
        return matches

    def find_device_for_local_ai(self, preferred_id: Optional[str] = None) -> Optional[str]:
        """Determine which device should handle local LLM inference.
        Prefers the user-specified device ID if available, otherwise queries for the 'local_llm' capability.
        """
        if preferred_id and preferred_id in self._devices:
            return preferred_id
        candidates = self.find_devices_by_capability("local_llm")
        if candidates:
            return candidates[0]
        # Fallback to remote worker or local device
        return self._default_remote_device if self._default_remote_device in self._devices else self._default_local_device

    def register_device(self, device: DeviceRecord):
        """Register or update a device record at runtime."""
        self._devices[device.id] = device
        self._alias_map[device.id.lower()] = device.id
        self._alias_map[device.display_name.lower()] = device.id
        for alias in device.aliases:
            self._alias_map[alias.lower().strip()] = device.id
        if device.is_local:
            self._default_local_device = device.id

    def unregister_device(self, device_id: str):
        """Remove a device and all its alias associations."""
        if device_id in self._devices:
            dev = self._devices.pop(device_id)
            keys_to_remove = [k for k, v in self._alias_map.items() if v == device_id]
            for k in keys_to_remove:
                self._alias_map.pop(k, None)

    def get_devices_prompt_summary(self) -> str:
        """Dynamically generate a clean, un-hardcoded summary of registered devices for LLM context."""
        lines = []
        for dev in self._devices.values():
            loc = "local host" if dev.is_local else "remote node"
            caps = ", ".join(dev.capabilities)
            lines.append(f"- \"{dev.id}\": {dev.display_name} ({dev.operating_system}, {loc}). Capabilities: [{caps}].")
        return "\n".join(lines)

    def resolve(self, phrase: Optional[str]) -> str:
        """Resolve a freeform mention or target string to a canonical device ID.
        If no target is given or unrecognized, returns the local device by default.
        """
        if not phrase:
            return self._default_local_device

        text = phrase.lower().strip()

        # 1. Exact alias match
        if text in self._alias_map:
            return self._alias_map[text]

        # 2. Check for alias substring inside phrase (longest matching alias first)
        sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text):
                return self._alias_map[alias]

        # 3. Heuristic fallback for generic terms
        if any(term in text for term in ("other", "secondary", "remote", "over there", "there")):
            return self._default_remote_device
        if any(term in text for term in ("this", "local", "here")):
            return self._default_local_device

        # Default to local
        return self._default_local_device

    def build_regex_pattern(self) -> str:
        """Build a dynamic non-capturing regex group matching all known aliases."""
        if not self._alias_map:
            return r"(?:local|remote)"
        sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)
        escaped = [re.escape(a) for a in sorted_aliases]
        return rf"(?:{'|'.join(escaped)})"
