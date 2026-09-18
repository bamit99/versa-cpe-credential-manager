"""API-level tests for the bulk rotation endpoint (bounded concurrency)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.v1.rotation import MAX_BULK_CPES, MAX_CONCURRENT_ROTATIONS
from app.auth.keycloak import TokenUser, get_current_user
from app.db.session import Base, get_db, get_session_factory
from app.models.credential import Credential
from app.services.secret_store.mock_vault import MockVaultStore


class RecordingClient:
    """Versa client that sleeps briefly and records max concurrent calls."""

    def __init__(self, stats: dict, lock: threading.Lock) -> None:
        self._stats = stats
        self._lock = lock

    def update_credential(self, cpe, password: str) -> bool:
        with self._lock:
            self._stats["active"] += 1
            self._stats["max"] = max(self._stats["max"], self._stats["active"])
        time.sleep(0.05)
        with self._lock:
            self._stats["active"] -= 1
        return True

    def verify_credential(self, cpe, password: str) -> bool:
        return True


@pytest.fixture()
def bulk_client(tmp_path: Path):
    vault_file = tmp_path / "vault.enc"

    # File-based SQLite so worker threads get independent connections with a busy timeout.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'bulk.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    shared_store = MockVaultStore(persist_path=vault_file)
    stats = {"active": 0, "max": 0}
    lock = threading.Lock()

    # Seed CPEs + active credentials.
    db = factory()
    from app.models.cpe import CPE

    for i in (1, 2, 3):
        cpe = CPE(cpe_id=f"CPE-ROT-{i}", device_name=f"dev-{i}", site="Lab", status="online")
        db.add(cpe)
        db.flush()
        ref = f"cred:rot-{i}"
        shared_store.create_secret(ref, f"v1-{i}")
        db.add(
            Credential(
                cpe_id=cpe.id,
                username="admin",
                secret_reference=ref,
                version=1,
                status="ACTIVE",
                rotation_state="ACTIVE",
                activated_at=None,
            )
        )
    db.commit()
    db.close()

    operator = TokenUser(subject="sub-ops", username="ops", roles=["security_operator"])

    def _override_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    import app.main as main_module

    app_obj = main_module.app
    app_obj.dependency_overrides[get_db] = _override_db
    app_obj.dependency_overrides[get_current_user] = lambda: operator
    app_obj.dependency_overrides[get_session_factory] = lambda: factory

    from app.api.v1.rotation import get_secret_store_factory, get_versa_client_factory

    app_obj.dependency_overrides[get_secret_store_factory] = lambda: (lambda _settings: shared_store)

    def _make_client(director, settings):
        return RecordingClient(stats, lock)

    app_obj.dependency_overrides[get_versa_client_factory] = lambda: _make_client

    yield TestClient(app_obj), factory, shared_store, stats

    app_obj.dependency_overrides.clear()
    db.close()


def _active_version(factory, cpe_id: str) -> int:
    from app.models.cpe import CPE

    db = factory()
    try:
        cpe = db.scalar(select(CPE).where(CPE.cpe_id == cpe_id))
        cred = db.scalar(
            select(Credential)
            .where(Credential.cpe_id == cpe.id, Credential.status == "ACTIVE")
            .order_by(Credential.version.desc())
        )
        return cred.version
    finally:
        db.close()


def test_bulk_rotate_all_success_with_bounded_concurrency(bulk_client):
    client, factory, shared_store, stats = bulk_client
    resp = client.post("/api/v1/bulk/rotate", json=["CPE-ROT-1", "CPE-ROT-2", "CPE-ROT-3"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested"] == 3
    assert {r["cpe_id"] for r in body["results"]} == {"CPE-ROT-1", "CPE-ROT-2", "CPE-ROT-3"}
    assert all(r["ok"] for r in body["results"])
    assert {r["version"] for r in body["results"]} == {2}
    # Workers ran in parallel (max_workers=5, batch=3) — never more than the cap.
    assert stats["max"] >= 2
    assert stats["max"] <= MAX_CONCURRENT_ROTATIONS
    # DB reflects the rotation for every CPE.
    for i in (1, 2, 3):
        assert _active_version(factory, f"CPE-ROT-{i}") == 2


def test_bulk_rotate_deduplicates_cpe_ids(bulk_client):
    client, *_ = bulk_client
    resp = client.post("/api/v1/bulk/rotate", json=["CPE-ROT-1", "CPE-ROT-1", "CPE-ROT-1"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested"] == 1
    assert len(body["results"]) == 1
    assert body["results"][0]["cpe_id"] == "CPE-ROT-1"
    assert body["results"][0]["ok"] is True


def test_bulk_rotate_rejects_oversized_batch(bulk_client):
    client, *_ = bulk_client
    too_many = [f"CPE-ROT-{i}" for i in range(MAX_BULK_CPES + 1)]
    resp = client.post("/api/v1/bulk/rotate", json=too_many)
    assert resp.status_code == 400
    assert "limited to" in resp.json()["detail"]


def test_bulk_rotate_empty_batch_is_noop(bulk_client):
    client, *_ = bulk_client
    resp = client.post("/api/v1/bulk/rotate", json=[])
    assert resp.status_code == 200
    assert resp.json() == {"requested": 0, "results": []}