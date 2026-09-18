"""Read-only integration status for the admin Integrations page.

Everything here is observational: it probes Keycloak (discovery + Admin REST
API for LDAP federation) and reports how the credential manager's own
dependencies are wired. It never mutates configuration -- LDAP/AD federation is
still registered in the Keycloak Admin Console.

Every network probe degrades gracefully: a failure yields a status object with
``available=False`` (or ``reachable=False``) and a human-readable ``detail``
rather than raising, so the page renders even when an integration is down.
"""
from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import parse_roles_json
from app.config import Settings, get_settings
from app.models.cpe import Director, User
from app.schemas.integration import (
    BreakGlassStatus,
    DirectorCredsStatus,
    IntegrationStatusOut,
    KeycloakStatus,
    LdapStatus,
    SecretStoreStatus,
)

_USER_STORAGE_PROVIDER = "org.keycloak.storage.UserStorageProvider"
_LDAP_PROVIDER_ID = "ldap"
_PROBE_TIMEOUT = 3.0


def _first(value: object) -> str | None:
    """Keycloak component config values are lists; normalise to a scalar."""
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


class IntegrationStatusService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._transport = transport

    @property
    def _admin_base(self) -> str:
        return (self._settings.keycloak_admin_url or self._settings.keycloak_url).rstrip("/")

    @property
    def _public_base(self) -> str:
        return (self._settings.keycloak_public_url or self._settings.keycloak_url).rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self._transport, timeout=_PROBE_TIMEOUT)

    def _console_url(self) -> str:
        return f"{self._public_base}/admin/{self._settings.keycloak_realm}/console"

    def _keycloak_status(self, client: httpx.Client) -> KeycloakStatus:
        url = (
            f"{self._settings.keycloak_url}/realms/{self._settings.keycloak_realm}"
            "/.well-known/openid-configuration"
        )
        try:
            resp = client.get(url)
            resp.raise_for_status()
            issuer = resp.json().get("issuer") or self._settings.issuer
            return KeycloakStatus(
                reachable=True,
                realm=self._settings.keycloak_realm,
                issuer=issuer,
                console_url=self._console_url(),
            )
        except (httpx.HTTPError, ValueError) as exc:
            return KeycloakStatus(
                reachable=False,
                realm=self._settings.keycloak_realm,
                issuer=self._settings.issuer,
                console_url=self._console_url(),
                detail=str(exc),
            )

    def _admin_token(self, client: httpx.Client) -> str:
        url = (
            f"{self._admin_base}/realms/{self._settings.keycloak_realm}"
            "/protocol/openid-connect/token"
        )
        resp = client.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._settings.keycloak_admin_client_id,
                "client_secret": self._settings.keycloak_admin_client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _ldap_status(self, client: httpx.Client) -> LdapStatus:
        try:
            token = self._admin_token(client)
            resp = client.get(
                f"{self._admin_base}/admin/realms/{self._settings.keycloak_realm}/components"
                f"?type={_USER_STORAGE_PROVIDER}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            components = resp.json()
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            return LdapStatus(
                admin_api_available=False,
                detail=(
                    "Keycloak Admin API unavailable -- configure a service account "
                    "(KEYCLOAK_ADMIN_CLIENT_ID / KEYCLOAK_ADMIN_CLIENT_SECRET) with "
                    f"view-realm to inspect user federation. Reason: {exc}"
                ),
            )

        providers = [
            c
            for c in components
            if isinstance(c, dict) and c.get("providerId") == _LDAP_PROVIDER_ID
        ]
        if not providers:
            return LdapStatus(
                admin_api_available=True,
                configured=False,
                detail="No LDAP provider registered. Add one in the Keycloak Admin Console.",
            )

        first = providers[0]
        config = first.get("config") or {}
        return LdapStatus(
            admin_api_available=True,
            configured=True,
            provider_names=[str(p.get("name", "")) for p in providers],
            connection_url=_first(config.get("connectionUrl")),
            edit_mode=_first(config.get("editMode")),
            enabled=(_first(config.get("enabled")) or "").lower() == "true",
        )

    def _secret_store_status(self) -> SecretStoreStatus:
        backend = self._settings.secret_store_type
        if backend == "mock_vault":
            return SecretStoreStatus(
                backend=backend,
                healthy=True,
                detail="In-memory encrypted store (development only).",
            )
        return SecretStoreStatus(
            backend=backend,
            healthy=False,
            detail="Adapter not implemented yet; only mock_vault is available.",
        )

    def _director_creds_status(self) -> DirectorCredsStatus:
        count = len(self._db.scalars(select(Director)).all())
        return DirectorCredsStatus(
            directors_count=count,
            api_username_configured=bool(self._settings.versa_api_username),
            mock_mode=self._settings.secret_store_type == "mock_vault",
            detail=(
                "Director console credentials are env-only; per-Director client "
                "credentials resolve from the secret store."
            ),
        )

    def _break_glass_status(self) -> BreakGlassStatus:
        users = self._db.scalars(select(User)).all()
        admin_count = sum(1 for u in users if "admin" in parse_roles_json(u.roles))
        return BreakGlassStatus(
            local_user_count=len(users),
            admin_count=admin_count,
            guidance=(
                "Local Keycloak accounts remain valid even when LDAP/AD is unavailable "
                "or unreachable; keep at least one local admin as break-glass."
            ),
        )

    def collect(self) -> IntegrationStatusOut:
        with self._client() as client:
            keycloak = self._keycloak_status(client)
            ldap = self._ldap_status(client)
        return IntegrationStatusOut(
            keycloak=keycloak,
            ldap=ldap,
            secret_store=self._secret_store_status(),
            director_creds=self._director_creds_status(),
            break_glass=self._break_glass_status(),
        )
