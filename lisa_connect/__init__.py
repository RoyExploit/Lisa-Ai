"""Lisa Connect subsystem.

This package adds the local gateway, device registry, pairing flow, and
protocol definitions used by Lisa AI to reach companion devices.
"""

from .service import LisaConnectService, get_service

__all__ = ["LisaConnectService", "get_service"]
