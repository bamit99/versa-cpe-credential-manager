"""Tests for Keycloak identity sync (HTTP flow + sync semantics)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.auth.keycloak import TokenUser
from app.services.identity_sync_service import IdentitySyncError, IdentitySyncService
from app.services.settings_service import SettingsService


def _make_transport(users: list[dict]) -> httpx.MockTransport:
    token_endpoint = "/realms/versa-telecom/protocol/openid-connect/token"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(token_endpoint):
            return httpx.Response(200, json={"access_token": "admin-tok"})
        if "/users/" in request.url.path and request.url.path.endswith("/role-mappings/realm"):
            user_id = request.url.path.split("/users/")[1].split("/")[0]
            rep = next(u for u in users if u["id"] == user_id)
            return httpx.Response(
                200,
                json=[{"name": r} for r in (rep.get("realmRoles") or []) if r != "offline_access"],
            )
        if request.url.path.endswith("/admin/realms/versa-telecom/users"):
            first = int(request.url.params.get("first", 0))
            max_ = int(request.url.params.get("max", 100))
            return httpx.Response(200, json=users[first : first + max_])
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


def test_sync_creates_and_updates_users(db_session, admin_user):
    users = [
        {
            "id": "u-1",
            "username": "admin",
            "email": "admin@example.test",
            "firstName": "Ada",
            "lastName": "Admin",
            "enabled": True,
            "realmRoles": ["admin"],
        },
        {
            "id": "u-2",
            "username": "field",
            "email": "field@example.test",
            "enabled": True,
            "realmRoles": [],
        },
    ]
    service = IdentitySyncService(db_session, transport=_make_transport(users))
    summary = service.sync(admin_user)

    assert summary == {"created": 2, "updated": 0, "total": 2}

    from sqlalchemy import select

    from app.models.cpe import User

    admin_row = db_session.scalar(select(User).where(User.subject == "u-1"))
    assert admin_row.username == "admin"
    assert json.loads(admin_row.roles) == ["admin"]
    assert admin_row.email == "admin@example.test"

    # field has no realmRoles → role-mappings called, returns none → empty roles
    field_row = db_session.scalar(select(User).where(User.subject == "u-2"))
    assert json.loads(field_row.roles) == []


def test_sync_uses_role_mapping_calls_when_realm_roles_missing(db_session, admin_user):
    users = [
        {
            "id": "u-ops",
            "username": "ops",
            "enabled": True,
            "firstName": "Op",
            "realmRoles": None,
        }
    ]
    transport = _make_transport(users)
    # Transport returns no roles for the mapping call since realmRoles is None → expected []
    service = IdentitySyncService(db_session, transport=transport)
    service.sync(admin_user)

    # region role mapping returned nothing → empty roles, not a crash
    from sqlalchemy import select

    from app.models.cpe import User

    row = db_session.scalar(select(User).where(User.subject == "u-ops"))
    assert row is not None
    assert json.loads(row.roles) == []


def test_sync_disables_deprovisioned_users(db_session, admin_user):
    from sqlalchemy import select

    from app.models.cpe import User

    db_session.add(
        User(subject="u-old", username="old", roles='["field_engineer"]', enabled=True)
    )
    db_session.commit()

    users = [{"id": "u-old", "username": "old", "enabled": False, "realmRoles": []}]
    service = IdentitySyncService(db_session, transport=_make_transport(users))
    service.sync(admin_user)

    row = db_session.scalar(select(User).where(User.subject == "u-old"))
    assert row.enabled is False


def test_sync_raises_when_token_exchange_fails(db_session, admin_user):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    service = IdentitySyncService(db_session, transport=httpx.MockTransport(handler))
    with pytest.raises(IdentitySyncError):
        service.sync(admin_user)


def test_sync_endpoint_round_trip(app_client, db_session, admin_user, monkeypatch):
    from app.services import identity_sync_service

    captured = {}
    calls = {"n": 0}

    class FakeService:
        def __init__(self, db, settings=None, transport=None):
            calls["n"] += 1
            captured["db"] = db
            captured["settings"] = settings

        def sync(self, actor):
            captured["actor"] = actor
            return {"created": 1, "updated": 0, "total": 1}

    monkeypatch.setattr(identity_sync_service, "IdentitySyncService", FakeService)

    resp = app_client.post("/api/v1/admin/sync/users")
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "updated": 0, "total": 1}
    assert calls["n"] == 1
    assert captured["actor"].subject == "sub-admin"