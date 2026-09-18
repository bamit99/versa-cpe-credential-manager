from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.keycloak import TokenUser
from app.config import get_settings
from app.db.session import Base
from app.models import *  # noqa: F401,F403  (register all models)
from app.services.secret_store.base import SecretStore
from app.services.secret_store.mock_vault import MockVaultStore
from app.adapters.versa.base import VersaClient
from app.adapters.versa.mock_versa import MockVersaClient

TEST_DB_URL = "sqlite://"


@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def secret_store(tmp_path) -> SecretStore:
    return MockVaultStore(persist_path=tmp_path / "vault.enc")


@pytest.fixture()
def versa_client() -> VersaClient:
    return MockVersaClient()


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def admin_user() -> TokenUser:
    return TokenUser(subject="sub-admin", username="admin", roles=["admin"])


@pytest.fixture()
def operator_user() -> TokenUser:
    return TokenUser(subject="sub-ops", username="ops", roles=["security_operator"])


@pytest.fixture()
def app_client(db_session, admin_user):
    """Per-test FastAPI test client sharing the db_session with the same overridden auth."""
    from fastapi.testclient import TestClient

    from app.auth.keycloak import get_current_user
    from app.db.session import get_db
    from app.main import app

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture()
def field_user() -> TokenUser:
    return TokenUser(subject="sub-field", username="field", roles=["field_engineer"])


@pytest.fixture()
def sample_director(db_session):
    from app.models.cpe import Director

    d = Director(
        name="VD-TEST-2213",
        host="127.0.0.1",
        api_base_url="https://127.0.0.1:9183",
        versa_version="22.1.3",
        oauth_client_id="test",
    )
    db_session.add(d)
    db_session.commit()
    return d


@pytest.fixture()
def sample_cpe(db_session, sample_director):
    from app.models.cpe import CPE

    c = CPE(
        cpe_id="CPE-TEST-0001",
        device_name="BR-DEV-01",
        serial_number="SN001",
        site="Lab",
        management_ip="10.9.9.9",
        director_id=sample_director.id,
        status="online",
    )
    db_session.add(c)
    db_session.commit()
    return c