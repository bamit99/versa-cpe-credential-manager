"""Keycloak identity sync: mirrors realm users (+ roles) into the local `users` table.

The admin service account must hold realm-management roles (query_users,
view-users, query-realms, …) against the configured realm.
"""
from __future__ import annotations

import json

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.config import Settings, get_settings
from app.models.cpe import User
from app.services.audit_service import AuditActions, AuditService

# Roles this application actually interprets; anything else is ignored on sync.
KNOWN_ROLES = {"admin", "security_operator", "field_engineer"}
_PAGE_SIZE = 100


class IdentitySyncError(Exception):
    pass


class IdentitySyncService:
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
    def _base(self) -> str:
        return self._settings.keycloak_admin_url or self._settings.keycloak_url

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self._transport)

    def _admin_token(self, client: httpx.Client) -> str:
        url = (
            f"{self._base}/realms/{self._settings.keycloak_realm}"
            "/protocol/openid-connect/token"
        )
        try:
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
        except (httpx.HTTPError, KeyError) as exc:
            raise IdentitySyncError(f"Unable to obtain Keycloak admin token: {exc}") from exc

    def _role_mappings(
        self, client: httpx.Client, headers: dict[str, str], user_id: str
    ) -> list[str]:
        url = (
            f"{self._base}/admin/realms/{self._settings.keycloak_realm}"
            f"/users/{user_id}/role-mappings/realm"
        )
        try:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise IdentitySyncError(f"Role mapping fetch failed for {user_id}: {exc}") from exc
        return [
            r["name"]
            for r in resp.json()
            if isinstance(r, dict) and r.get("name") in KNOWN_ROLES
        ]

    def fetch_users(self, client: httpx.Client, headers: dict[str, str]) -> list[dict]:
        """Paginate the realm's /admin/realms/{realm}/users endpoint."""
        users: list[dict] = []
        first = 0
        while True:
            url = (
                f"{self._base}/admin/realms/{self._settings.keycloak_realm}/users"
                f"?first={first}&max={_PAGE_SIZE}"
            )
            try:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise IdentitySyncError(f"User list fetch failed: {exc}") from exc
            page = resp.json()
            users.extend(page)
            if len(page) < _PAGE_SIZE:
                break
            first += _PAGE_SIZE
        return users

    def sync(self, actor: TokenUser) -> dict:
        with self._client() as client:
            token = self._admin_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            reps = self.fetch_users(client, headers)

            created = 0
            updated = 0
            for rep in reps:
                user_id = rep.get("id")
                username = rep.get("username", "")
                if not user_id or not username:
                    continue
                roles = [r for r in rep.get("realmRoles") or [] if r in KNOWN_ROLES]
                if not roles:
                    roles = self._role_mappings(client, headers, user_id)
                enabled = bool(rep.get("enabled", True))

                row = self._db.scalar(select(User).where(User.subject == user_id))
                if row is None:
                    self._db.add(
                        User(
                            subject=user_id,
                            username=username,
                            email=rep.get("email"),
                            first_name=rep.get("firstName"),
                            last_name=rep.get("lastName"),
                            roles=json.dumps(roles),
                            enabled=enabled,
                        )
                    )
                    created += 1
                else:
                    row.username = username
                    row.email = rep.get("email")
                    row.first_name = rep.get("firstName")
                    row.last_name = rep.get("lastName")
                    row.roles = json.dumps(roles)
                    row.enabled = enabled
                    updated += 1
        self._db.commit()

        AuditService(self._db).record(
            action=AuditActions.IDENTITY_SYNCED,
            user=actor,
            metadata_json=json.dumps(
                {"created": created, "updated": updated, "total": len(reps)}
            ),
        )
        return {"created": created, "updated": updated, "total": len(reps)}