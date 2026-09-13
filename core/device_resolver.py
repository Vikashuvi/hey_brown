"""Dynamic Device Resolution System for Brown.
Resolves user device mentions and configured aliases to canonical device IDs.
No device names or aliases are hard-coded in logic.
"""

from typing import Dict, Any, List, Optional
import re


DEFAULT_DEVICES_CONFIG: Dict[str, Any] = {
    "paperball": {
        "id": "paperball",
        "display_name": "Paperball",
        "is_local": True,
        "aliases": [
            "paperball", "mac", "macbook", "laptop", "local", "locally", "here",
            "this machine", "this computer", "mac os", "macos"
        ],
    },
    "error_boy": {
        "id": "error_boy",
        "display_name": "Error Boy",
        "is_local": False,
        "aliases": [
            "error boy", "error_boy", "error", "linux laptop", "linux machine",
            "linux", "secondary laptop", "secondary machine", "secondary", "other laptop",
            "other machine", "other computer", "arch linux", "arch", "victus", "pc", "forge"
        ],
    },

}


class DeviceResolver:
    """Dynamically resolves device mentions to canonical device IDs based on configuration."""

    def __init__(self, devices_config: Optional[Dict[str, Any]] = None):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._alias_map: Dict[str, str] = {}
        self._default_local_device = "paperball"
        self._default_remote_device = "error_boy"
        cfg = devices_config if devices_config else DEFAULT_DEVICES_CONFIG
        self.update_config(cfg)


    def update_config(self, devices_config: Dict[str, Any]):
        """Load or update device definitions and alias mappings from configuration."""
        self._devices = {}
        self._alias_map = {}

        for dev_id, dev_data in devices_config.items():
            if not isinstance(dev_data, dict):
                continue
            canonical_id = dev_data.get("id", dev_id)
            display_name = dev_data.get("display_name", canonical_id)
            is_local = dev_data.get("is_local", False)

            if is_local:
                self._default_local_device = canonical_id
            else:
                self._default_remote_device = canonical_id

            self._devices[canonical_id] = {
                "id": canonical_id,
                "display_name": display_name,
                "is_local": is_local,
                "aliases": dev_data.get("aliases", []),
            }

            # Map canonical ID itself and display name
            self._alias_map[canonical_id.lower()] = canonical_id
            self._alias_map[display_name.lower()] = canonical_id

            # Map all declared aliases
            for alias in dev_data.get("aliases", []):
                self._alias_map[alias.lower().strip()] = canonical_id

    @property
    def registered_devices(self) -> List[str]:
        return list(self._devices.keys())

    @property
    def default_local_device(self) -> str:
        return self._default_local_device

    @property
    def default_remote_device(self) -> str:
        return self._default_remote_device

    def get_display_name(self, device_id: str) -> str:
        info = self._devices.get(device_id)
        if info:
            return info.get("display_name", device_id)
        return device_id

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
            # Word-boundary or substring match
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text):
                return self._alias_map[alias]

        # 3. Heuristic fallback for generic terms
        if any(term in text for term in ("other", "secondary", "remote", "linux", "over there", "there")):
            return self._default_remote_device
        if any(term in text for term in ("this", "local", "here", "mac")):
            return self._default_local_device

        # Default to local
        return self._default_local_device

    def build_regex_pattern(self) -> str:
        """Build a dynamic non-capturing regex group matching all known aliases."""
        if not self._alias_map:
            return r"(?:paperball|error_boy)"
        sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)
        escaped = [re.escape(a) for a in sorted_aliases]
        return rf"(?:{'|'.join(escaped)})"
