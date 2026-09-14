"""Device agent interfaces and command result models.
Authoritative definitions are in agents.base; this module re-exports them
for backward compatibility and clean cross-package imports.
"""

from agents.base import DeviceCommandResult, DeviceAgent

__all__ = ["DeviceCommandResult", "DeviceAgent"]
