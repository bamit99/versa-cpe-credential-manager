"""Real Versa Director REST client for 22.1.3 / 22.1.4 (pre-23.1.1 protocol).

Auth: OAuth password grant per `docs/versa-version-matrix.md`:
    POST {api_base_url}/auth/token  (client_id, client_secret, username, password)

Discovery: `GET /vnms/sdwan/vnf/cpes` — path verified in published Swagger for
both releases, but the exact response shape and field names are LAB-VERIFIED-only.
This implementation parses defensively: it accepts either a JSON list of devices
or an object holding them under a `device` key, and maps whatever identifiers are
available so a shape mismatch degrades gracefully instead of failing the sync.

Credential change (`change-password`) and verification remain TO VERIFY in lab;
those methods raise rather than guess.
"""
from __future__ import annotations

import logging

import httpx

from app.adapters.versa.base import VersaClient
from app.config import Settings, get_settings
from app.models.cpe import CPE, Director
from app.services.secret_store.base import SecretStore

logger = logging.getLogger(__name__)


class VersaDirectorPre23Client(VersaClient):
    def __init__(
        self,
        director: Director,
        settings: Settings | None = None,
        secret_store: SecretStore | None = None,
        username: str = "",
        password: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._director = director
        self._settings = settings or get_settings()
        self._secret_store = secret_store
        self._username = username or self._settings.versa_api_username
        self._password = password or self._settings.versa_api_password
        # Self-signed Directors are expected in lab environments; certificate
        # verification follows debug mode until corporate PKI is wired.
        self._client = httpx.Client(transport=transport, verify=self._settings.debug)

    def _token(self) -> str:
        url = f"{self._director.api_base_url.rstrip('/')}/auth/token"
        client_secret = self._director.oauth_secret_ref
        if client_secret and self._secret_store is not None:
            try:
                client_secret = self._secret_store.get_secret(client_secret)
            except Exception:  # noqa: BLE001 - never let secret resolution break discovery
                logger.warning("Could not resolve oauth_secret_ref for %s", self._director.name)
                client_secret = ""
        data: dict[str, str] = {
            "grant_type": "password",
            "client_id": self._director.oauth_client_id,
            "username": self._username,
            "password": self._password,
        }
        if client_secret:
            data["client_secret"] = client_secret
        resp = self._client.post(url, data=data, timeout=15.0)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def discover_devices(self, director: Director) -> list[dict]:
        del director  # bound in constructor
        url = f"{self._director.api_base_url.rstrip('/')}/vnms/sdwan/vnf/cpes"
        resp = self._client.get(url, headers=self._headers(), timeout=30.0)
        resp.raise_for_status()
        payload = resp.json()
        devices = payload if isinstance(payload, list) else (payload.get("device") or [])
        return [self._map_device(d) for d in devices if isinstance(d, dict)]

    @staticmethod
    def _map_device(d: dict) -> dict:
        """Best-effort mapping of a VD device record to a CPE row.

        Field names are candidate-only until lab verification; every lookup is
        tolerant (None when absent) so the sync never throws on shape drift.
        """
        cpe_id = (
            d.get("deviceName")
            or d.get("name")
            or d.get("hostname")
            or d.get("serialNumber")
            or d.get("serial")
        )
        serial = d.get("serialNumber") or d.get("serial")
        mgmt_ip = d.get("managementIp") or d.get("managementIP") or d.get("ipAddress")
        return {
            "cpe_id": str(cpe_id) if cpe_id is not None else "",
            "device_name": d.get("displayName") or d.get("hostname"),
            "serial_number": str(serial) if serial is not None else None,
            "site": d.get("organizationName") or d.get("org"),
            "management_ip": mgmt_ip,
            "status": "online" if str(d.get("operationalStatus", "")).lower() in {"up", "online"} else "unknown",
        }

    def update_credential(self, cpe: CPE, new_password: str) -> bool:
        raise NotImplementedError(
            "Credential change via the Director API is TO VERIFY in lab (22.1.3/22.1.4)"
        )

    def verify_credential(self, cpe: CPE, password: str) -> bool:
        raise NotImplementedError(
            "Credential verification via the Director API is TO VERIFY in lab"
        )

    def get_device_status(self, cpe: CPE) -> dict:
        raise NotImplementedError(
            "Device status via the Director API is TO VERIFY in lab"
        )