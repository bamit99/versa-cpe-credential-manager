"""Versa Director client interface.

Implementations:
  - MockVersaClient: for dev/test (always succeeds; no real Versa calls).
  - VersaDirectorPre23Client: covers 22.1.3 and 22.1.4 (TO IMPLEMENT after lab verification).

All Versa-specific logic lives in this module tree; the rest of the application
calls through this interface only.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from app.config import Settings, get_settings
from app.models.cpe import CPE, Director
from app.services.secret_store.base import SecretStore

logger = logging.getLogger(__name__)


class VersaClient(ABC):
    @abstractmethod
    def update_credential(self, cpe: CPE, new_password: str) -> bool:
        """Push a new credential to the CPE via the Director. Returns True on success."""

    @abstractmethod
    def verify_credential(self, cpe: CPE, password: str) -> bool:
        """Attempt authentication against the CPE to verify the new credential works."""

    @abstractmethod
    def get_device_status(self, cpe: CPE) -> dict:
        """Fetch device status from the Director."""

    @abstractmethod
    def discover_devices(self, director: Director) -> list[dict]:
        """Pull the full CPE inventory from the Director (used by sync)."""


def build_versa_client(
    director: Director | None = None,
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
) -> VersaClient:
    settings = settings or get_settings()
    # In development (mock vault) we never touch a real Director.
    if settings.secret_store_type == "mock_vault" or director is None:
        from app.adapters.versa.mock_versa import MockVersaClient
        return MockVersaClient()
    from app.adapters.versa.director22 import VersaDirectorPre23Client
    return VersaDirectorPre23Client(director, settings, secret_store)