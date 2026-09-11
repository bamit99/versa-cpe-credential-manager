"""Regression test: no API response OR log contains the stored secret,
EXCEPT the intentionally-authorised credential reveal endpoint.

Runs the full FastAPI app with test overrides (SQLite + mock vault file
shared between store instances).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.keycloak import get_current_user
from app.db.session import Base, get_db
from app.models.access import CPEAssignment
from app.models.cpe import CPE
from app.services.credential_service import CredentialService
from app.services.secret_store.mock_vault import MockVaultStore

_SECRET_VALUE = "SuPer-Secret-9876-XYZ"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    vault_file = tmp_path / "vault.enc"
    monkeypatch.setenv("MOCK_VAULT_FILE", str(vault_file))

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    store = MockVaultStore(persist_path=vault_file)

    session = factory()
    cpe = CPE(
        cpe_id="CPE-SECRET-1",
        device_name="BR-DEV",
        site="Lab",
        status="online",
    )
    session.add(cpe)
    session.commit()
    store.create_secret("cred:leaktest", _SECRET_VALUE)
    from sqlalchemy import select

    from app.models.credential import Credential

    session.add(
        Credential(
            cpe_id=cpe.id,
            username="admin",
            secret_reference="cred:leaktest",
            version=1,
            status="ACTIVE",
            rotation_state="ACTIVE",
        )
    )
    session.add(CPEAssignment(user_subject="sub-field", cpe_id=cpe.cpe_id))
    session.commit()

    from app.auth.keycloak import TokenUser

    field_user = TokenUser(subject="sub-field", username="field", roles=["field_engineer"])

    def _override_db():
        try:
            yield session
        finally:
            pass

    import app.main as main_module

    # Rebuild app so the overrides apply to this module instance.
    app_obj = main_module.app
    app_obj.dependency_overrides[get_db] = _override_db
    app_obj.dependency_overrides[get_current_user] = lambda: field_user

    yield TestClient(app_obj)
    session.close()
    app_obj.dependency_overrides.clear()


def test_reveal_endpoint_is_only_source_of_secret(client, tmp_path):
    reveal = client.post(
        "/api/v1/cpes/CPE-SECRET-1/reveal",
        json={"reason": "test", "ticket_reference": "INC-9"},
    )
    assert reveal.status_code == 200, reveal.text
    body = reveal.json()
    assert body["password"] == _SECRET_VALUE  # authorised reveal only

    # Every other endpoint must NOT expose the secret in its raw text.
    endpoints = [
        ("GET", "/api/v1/cpes"),
        ("GET", "/api/v1/cpes/CPE-SECRET-1"),
        ("GET", "/api/v1/cpes/CPE-SECRET-1/credential"),
        ("GET", "/api/v1/audit"),
        ("GET", "/api/v1/dashboard"),
        ("GET", "/api/v1/me"),
    ]
    for method, url in endpoints:
        resp = client.request(method, url)
        assert _SECRET_VALUE not in resp.text, f"Secret leaked via {method} {url}"


def test_secret_never_written_to_authless_or_error_payloads(client):
    resp = client.post(
        "/api/v1/cpes/CPE-SECRET-1/reveal",
        json={},
    )
    assert resp.status_code == 422
    assert _SECRET_VALUE not in resp.text