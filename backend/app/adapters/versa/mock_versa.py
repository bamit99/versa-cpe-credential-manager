"""Mock Versa Director client (development/test only).

Always succeeds. Records mock operations in the logger only.
"""
from __future__ import annotations

import logging
import uuid

from app.models.cpe import CPE, Director

from app.adapters.versa.base import VersaClient

logger = logging.getLogger(__name__)


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
        logger.info("[MOCK] discover_devices on %s — returning empty list", director.name)
        return []