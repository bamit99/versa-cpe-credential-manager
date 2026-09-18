"""Tests for the read-only admin Integrations status surface."""
from __future__ import annotations

import httpx

from app.config import Settings
from app.services.integration_service import IntegrationStatusService


def _settings(**overrides) -> Settings:
    base = {
        "keycloak_url": "http://kc:8080/auth",
        "keycloak_realm": "versa-telecom",
        "keycloak_public_url": "https://localhost:8443/auth",
        "keycloak_admin_client_id": "svc-account",
        "keycloak_admin_client_secret": "secret",
    }
    base.update(overrides)
    return Settings(**base)


def _handler(components, token_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200, json={"issuer": "https://localhost:8443/auth/realms/versa-telecom"}
            )
        if path.endswith("/protocol/openid-connect/token"):
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "unauthorized"})
            return httpx.Response(200, json={"access_token": "t"})
        if path.endswith("/components"):
            return httpx.Response(200, json=components)
        return httpx.Response(404)

    return handler


def _ldap_component() -> dict:
    return {
        "name": "corp-ad",
        "providerId": "ldap",
        "config": {
            "connectionUrl": ["ldaps://ad.corp.example:636"],
            "editMode": ["READ_ONLY"],
            "enabled": ["true"],
        },
    }


def test_collect_reports_ldap_federation(db_session):
    svc = IntegrationStatusService(
        db_session, settings=_settings(), transport=httpx.MockTransport(_handler([_ldap_component()]))
    )
    out = svc.collect()

    assert out.keycloak.reachable is True
    assert out.keycloak.console_url == "https://localhost:8443/auth/admin/versa-telecom/console"
    assert out.ldap.admin_api_available is True
    assert out.ldap.configured is True
    assert out.ldap.provider_names == ["corp-ad"]
    assert out.ldap.connection_url == "ldaps://ad.corp.example:636"
    assert out.ldap.edit_mode == "READ_ONLY"
    assert out.ldap.enabled is True


def test_collect_reports_ldap_absent(db_session):
    svc = IntegrationStatusService(
        db_session,
        settings=_settings(),
        transport=httpx.MockTransport(_handler([{"name": "other", "providerId": "kerberos"}])),
    )
    out = svc.collect()

    assert out.ldap.admin_api_available is True
    assert out.ldap.configured is False
    assert out.ldap.provider_names == []


def test_collect_degrades_when_admin_api_denies(db_session):
    svc = IntegrationStatusService(
        db_session,
        settings=_settings(),
        transport=httpx.MockTransport(_handler([_ldap_component()], token_status=401)),
    )
    out = svc.collect()

    assert out.keycloak.reachable is True
    assert out.ldap.admin_api_available is False
    assert out.ldap.configured is None
    assert "service account" in out.ldap.detail


def test_collect_degrades_when_keycloak_unreachable(db_session):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    svc = IntegrationStatusService(
        db_session, settings=_settings(), transport=httpx.MockTransport(boom)
    )
    out = svc.collect()

    assert out.keycloak.reachable is False
    assert out.keycloak.detail
    assert out.ldap.admin_api_available is False


def test_break_glass_and_store_status(db_session):
    from app.models.cpe import User

    db_session.add(User(subject="a", username="admin", roles='["admin"]'))
    db_session.add(User(subject="b", username="ops", roles='["security_operator"]'))
    db_session.commit()

    def _unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network in unit tests")

    out = IntegrationStatusService(
        db_session, settings=_settings(), transport=httpx.MockTransport(_unreachable)
    ).collect()

    assert out.secret_store.backend == "mock_vault"
    assert out.secret_store.healthy is True
    assert out.break_glass.local_user_count == 2
    assert out.break_glass.admin_count == 1
    assert out.director_creds.directors_count == 0
    assert out.director_creds.mock_mode is True


def test_integrations_endpoint_returns_status(app_client, db_session):
    import app.main as main_module
    from app.api.v1 import admin as admin_module

    svc = IntegrationStatusService(
        db_session, settings=_settings(), transport=httpx.MockTransport(_handler([_ldap_component()]))
    )
    overrides = main_module.app.dependency_overrides
    overrides[admin_module.get_integration_service] = lambda: svc
    try:
        resp = app_client.get("/api/v1/admin/integrations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ldap"]["configured"] is True
        assert body["keycloak"]["realm"] == "versa-telecom"
    finally:
        overrides.pop(admin_module.get_integration_service, None)


def test_integrations_endpoint_forbidden_for_non_admin(app_client):
    import app.main as main_module
    from app.auth.keycloak import TokenUser, get_current_user

    overrides = main_module.app.dependency_overrides
    overrides[get_current_user] = lambda: TokenUser(
        subject="sub-field", username="field", roles=["field_engineer"]
    )
    try:
        assert app_client.get("/api/v1/admin/integrations").status_code == 403
    finally:
        overrides.pop(get_current_user, None)
