"""SecretStore abstraction.

The application NEVER stores credential values itself. Only a `secret_reference`
is persisted. Concrete implementations are replaceable at runtime via
`SECRET_STORE_TYPE`:
  - mock_vault  (DEV ONLY, in-memory + encrypted at rest)
  - cyberark    (future)
  - hsm/kms     (future)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.config import Settings

logger = logging.getLogger(__name__)


class SecretStoreError(Exception):
    pass


class SecretNotFoundError(SecretStoreError):
    pass


class SecretStore(ABC):
    """Interface for the secret-storage backend."""

    @abstractmethod
    def create_secret(self, reference: str, value: str, metadata: dict | None = None) -> None:
        """Store a secret under `reference`."""

    @abstractmethod
    def get_secret(self, reference: str) -> str | None:
        """Retrieve a secret value (returns None if missing)."""

    @abstractmethod
    def update_secret(self, reference: str, value: str) -> None:
        """Replace the secret value at `reference`."""

    @abstractmethod
    def delete_secret(self, reference: str) -> None:
        """Remove the secret at `reference`."""

    @abstractmethod
    def rotate_secret(self, reference: str, new_value: str, keep_old: bool = False) -> None:
        """Rotate to `new_value`; optionally retain the previous version."""


def build_secret_store(settings: Settings) -> SecretStore:
    store_type = settings.secret_store_type
    if store_type == "mock_vault":
        from app.services.secret_store.mock_vault import MockVaultStore

        logger.warning("Using DEV-ONLY mock vault secret store. NOT for production use.")
        return MockVaultStore()
    # Future backends registered here:
    # if store_type == "cyberark": ...
    raise ValueError(f"Unsupported SECRET_STORE_TYPE: {store_type!r}")