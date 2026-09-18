"""Mock Versa Director client (development/test only).

Always succeeds. Records mock operations in the logger only.
"""
from __future__ import annotations

import logging
import re

from app.models.cpe import CPE, Director

from app.adapters.versa.base import VersaClient

logger = logging.getLogger(__name__)


def _tag_for(director: Director) -> str:
    """Stable short token from the director name so discovery is deterministic."""
    tag = re.sub(r"[^A-Za-z0-9]", "", director.name)
    return (tag[:8] or "VD").upper()


class MockVersaClient(VersaClient):
    def update_credential(self, cpe: CPE, new_password: str) -> bool:
        logger.info("[MOCK] update_credential for %s (new password not logged)", cpe.cpe_id)
        return True

    def verify_credential(self, cpe: CPE, password: str) -> bool:
        logger.info("[MOCK] verify_credential for %s (password not logged)", cpe.cpe_id)
        return True

    def get_device_status(self, cpe: CPE) -> dict:
        return {"cpe_id": cpe.cpe_id, "status": "online", "mock": True}

    def discover_devices(self, director: Director) -> list[dict]:
        tag = _tag_for(director)
        logger.info("[MOCK] discover_devices on %s — returning generated catalogue", director.name)
        devices = []
        for n in range(1, 6):
            devices.append(
                {
                    "cpe_id": f"CPE-{tag}-{n:03d}",
                    "device_name": f"BR-{tag}-{n:02d}",
                    "serial_number": f"VS-{tag}-{n:08d}",
                    "site": "Discovered",
                    "management_ip": f"10.200.0.{n}",
                    "status": "online" if n % 3 else "offline",
                }
            )
        return devices