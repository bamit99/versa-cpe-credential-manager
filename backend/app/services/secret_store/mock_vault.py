"""DEV-ONLY in-memory SecretStore.

This is NOT a production secret store. It is an encrypted in-memory map used so
the MVP runs locally without a real vault backend. It deliberately lacks the
properties of a real vault (KMS-backed keys, audit-at-store, HA, off-box
storage) and must never back a production deployment.

The on-disk persistence file is encrypted with a runtime-derived key, so even a
leaked file does not expose plaintext credential material.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.services.secret_store.base import SecretNotFoundError, SecretStore

_DEV_PERSIST_PATH_ENV = "MOCK_VAULT_FILE"
_DEV_PASSPHRASE_ENV = "MOCK_VAULT_PASSPHRASE"
_DEV_PERSIST_DEFAULT = "/tmp/mock_vault.enc"
_DEV_PASSPHRASE_DEFAULT = "versa-dev-insecure"


def _default_persist_path() -> Path:
    return Path(os.environ.get(_DEV_PERSIST_PATH_ENV, _DEV_PERSIST_DEFAULT))


def _derive_key(passphrase: str | None = None) -> bytes:
    """Derive an encryption key from a dev-only environment passphrase."""
    passphrase = passphrase or os.environ.get(_DEV_PASSPHRASE_ENV, _DEV_PASSPHRASE_DEFAULT)
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class MockVaultStore(SecretStore):
    def __init__(self, persist_path: Path | None = None, passphrase: str | None = None) -> None:
        self._path = persist_path or _default_persist_path()
        self._fernet = Fernet(_derive_key(passphrase))
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = self._fernet.decrypt(self._path.read_bytes())
            self._data = json.loads(payload.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, OSError):
            # Corrupt or unreadable dev artifact: start empty rather than crash.
            self._data = {}

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            token = self._fernet.encrypt(json.dumps(self._data).encode("utf-8"))
            self._path.write_bytes(token)
        except OSError:
            pass  # in-memory only fallback; dev convenience

    def create_secret(self, reference: str, value: str, metadata: dict | None = None) -> None:
        if reference in self._data:
            raise SecretNotFoundError(f"Secret reference already exists: {reference}")
        self._data[reference] = value
        self._persist()

    def get_secret(self, reference: str) -> str | None:
        return self._data.get(reference)

    def update_secret(self, reference: str, value: str) -> None:
        if reference not in self._data:
            raise SecretNotFoundError(f"Secret reference not found: {reference}")
        self._data[reference] = value
        self._persist()

    def delete_secret(self, reference: str) -> None:
        self._data.pop(reference, None)
        self._persist()

    def rotate_secret(self, reference: str, new_value: str, keep_old: bool = False) -> None:
        if reference not in self._data:
            raise SecretNotFoundError(f"Secret reference not found: {reference}")
        if keep_old:
            self._data[f"{reference}__prev"] = self._data[reference]
        self._data[reference] = new_value
        self._persist()