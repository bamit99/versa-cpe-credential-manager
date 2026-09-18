"""API-level tests for admin surfaces (directors, assignments, users)."""
from __future__ import annotations


def _seed_user(db_session, subject="sub-field", username="field") -> None:
    from app.models.cpe import User

    db_session.add(
        User(subject=subject, username=username, email=f"{username}@example.test", roles='["field_engineer"]')
    )
    db_session.commit()


def test_director_create_update_toggle_and_capabilities(app_client, db_session):
    body = {
        "name": "VD-2214",
        "host": "vd.example.test",
        "api_base_url": "https://vd.example.test:9183",
        "versa_version": "22.1.4",
        "oauth_client_id": "cpe-mgr",
        "oauth_secret_ref": "secret:vd",
    }
    resp = app_client.post("/api/v1/admin/directors", json=body)
    assert resp.status_code == 201
    director = resp.json()
    assert director["versa_version"] == "22.1.4"
    assert director["enabled"] is True
    assert director["capabilities"] == {}

    # Toggle off + version bump via PUT.
    resp = app_client.put(
        f"/api/v1/admin/directors/{director['id']}",
        json={"enabled": False, "versa_version": "22.1.3"},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["versa_version"] == "22.1.3"

    # List reflects it.
    resp = app_client.get("/api/v1/admin/directors")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_director_status_probe_unreachable(app_client, db_session):
    from app.models.cpe import Director

    d = Director(
        name="VD-OFFLINE",
        host="127.0.0.1",
        api_base_url="https://127.0.0.1:1",
        versa_version="22.1.3",
        oauth_client_id="x",
    )
    db_session.add(d)
    db_session.commit()

    resp = app_client.get(f"/api/v1/admin/directors/{d.id}/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["reachable"] is False
    assert payload["detail"]


def test_assignment_lifecycle_and_audit(app_client, db_session):
    from sqlalchemy import select

    from app.models.access import CPEAssignment
    from app.models.audit import AuditEvent

    _seed_user(db_session)
    # CPE via admin client (admin_user fixture), need to seed directly.
    from app.models.cpe import CPE

    db_session.add(
        CPE(cpe_id="CPE-A-1", device_name="BR-1", site="Site A", status="online")
    )
    db_session.commit()

    resp = app_client.post(
        "/api/v1/admin/assignments",
        json={"user_subject": "sub-field", "cpe_id": "CPE-A-1"},
    )
    assert resp.status_code == 201
    assert db_session.scalar(select(CPEAssignment.id).where(CPEAssignment.cpe_id == "CPE-A-1"))

    # List joins username + device name.
    resp = app_client.get("/api/v1/admin/assignments")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["cpe_id"] == "CPE-A-1"
    assert rows[0]["username"] == "field"
    assert rows[0]["device_name"] == "BR-1"

    # Unassign.
    resp = app_client.request(
        "DELETE",
        "/api/v1/admin/assignments",
        json={"user_subject": "sub-field", "cpe_id": "CPE-A-1"},
    )
    assert resp.status_code == 200
    assert db_session.scalar(select(CPEAssignment.id).where(CPEAssignment.cpe_id == "CPE-A-1")) is None

    events = list(
        db_session.scalars(
            select(AuditEvent)
            .where(AuditEvent.action.in_(["CPE_ASSIGNED", "CPE_UNASSIGNED"]))
            .order_by(AuditEvent.id)
        )
    )
    assert [e.action for e in events] == ["CPE_ASSIGNED", "CPE_UNASSIGNED"]


def test_assign_missing_cpe_404(app_client, db_session):
    resp = app_client.post(
        "/api/v1/admin/assignments",
        json={"user_subject": "sub-field", "cpe_id": "DOES-NOT-EXIST"},
    )
    assert resp.status_code == 404


def test_admin_users_listing(app_client, db_session):
    _seed_user(db_session)
    from app.models.cpe import User

    db_session.add(User(subject="sub-admin", username="admin", roles='["admin"]'))
    db_session.commit()

    resp = app_client.get("/api/v1/admin/users")
    assert resp.status_code == 200
    by_username = {u["username"]: u for u in resp.json()}
    assert by_username["field"]["roles"] == ["field_engineer"]
    assert by_username["admin"]["roles"] == ["admin"]


def test_sync_cpes_pulls_inventory_and_audits(app_client, db_session):
    from sqlalchemy import select

    from app.models.audit import AuditEvent
    from app.models.cpe import CPE

    d = _make_director(db_session)
    resp = app_client.post(f"/api/v1/admin/directors/{d.id}/sync-cpes")
    assert resp.status_code == 200
    assert resp.json() == {"discovered": 5, "created": 5, "updated": 0}

    ids = {c.cpe_id for c in db_session.scalars(select(CPE)).all()}
    assert any(i.startswith("CPE-") and i.endswith("001") for i in ids)
    assert len(ids) == 5

    # Idempotent second pull → updates only.
    resp = app_client.post(f"/api/v1/admin/directors/{d.id}/sync-cpes")
    assert resp.json() == {"discovered": 5, "created": 0, "updated": 5}

    events = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "CPE_DISCOVERED")
        )
    )
    assert len(events) == 2
    import json

    assert json.loads(events[0].metadata_json)["created"] == 5


def test_sync_cpes_unknown_director_404(app_client, db_session):
    resp = app_client.post("/api/v1/admin/directors/99999/sync-cpes")
    assert resp.status_code == 404


def _make_director(db_session):
    from app.models.cpe import Director

    d = Director(
        name="VD-DISCOVERY",
        host="director-discovery.example.test",
        api_base_url="https://director-discovery.example.test:9183",
        versa_version="22.1.4",
        oauth_client_id="cpe-manager",
    )
    db_session.add(d)
    db_session.commit()
    return d


def test_non_admin_forbidden_on_admin_surface(app_client, db_session):
    # swap override to a field engineer
    import app.main as main_module

    from app.auth.keycloak import TokenUser, get_current_user

    app_obj = main_module.app
    app_obj.dependency_overrides[get_current_user] = lambda: TokenUser(
        subject="sub-field", username="field", roles=["field_engineer"]
    )
    try:
        assert app_client.get("/api/v1/admin/users").status_code == 403
        assert app_client.get("/api/v1/admin/password-policy").status_code == 403
    finally:
        app_obj.dependency_overrides[get_current_user] = None
        app_obj.dependency_overrides.pop(get_current_user, None)