from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.services.rotation_service import RotationService
from app.services.settings_service import SettingsService
from app.utils.crypto import PasswordPolicy, policy_from_dict, policy_to_dict


def _roundtrip(policy: PasswordPolicy, db: Session):
    service = SettingsService(db)
    service.set_password_policy(policy)
    return service.get_password_policy()


def test_password_policy_serialization_roundtrip():
    p = PasswordPolicy(length=32, min_lower=2, min_upper=2, min_digit=2, min_special=2)
    back = policy_from_dict(policy_to_dict(p))
    assert back == p


def test_password_policy_from_dict_uses_defaults_for_missing_keys():
    back = policy_from_dict({"length": 28})
    assert back.length == 28
    assert back.min_lower == 1


def test_password_policy_rejects_impossible_constraints():
    with pytest.raises(ValueError):
        PasswordPolicy(length=12, min_special=50).validate()
    with pytest.raises(ValueError):
        policy_from_dict({"length": 12, "min_lower": 5, "min_upper": 5, "min_digit": 5, "min_special": 5})


def test_settings_service_defaults_when_unset(db_session):
    policy = SettingsService(db_session).get_password_policy()
    assert policy == PasswordPolicy()


def test_settings_service_roundtrip(db_session):
    p = PasswordPolicy(length=32, min_lower=2, min_upper=2, min_digit=2, min_special=2)
    assert _roundtrip(p, db_session) == p
    assert SettingsService(db_session).get_password_policy() == p


def test_settings_service_update_persists(db_session):
    service = SettingsService(db_session)
    service.set_password_policy(PasswordPolicy(length=28))
    service.set_password_policy(PasswordPolicy(length=40))
    assert service.get_password_policy().length == 40


def test_credential_service_reads_persisted_policy(db_session, secret_store, sample_cpe, admin_user):
    from app.services.credential_service import CredentialService

    SettingsService(db_session).set_password_policy(PasswordPolicy(length=36))
    service = CredentialService(db_session, secret_store)
    assert service._policy.length == 36
    cred = service.create_for_cpe(sample_cpe, "admin", admin_user)
    secret = secret_store.get_secret(cred.secret_reference)
    assert len(secret) == 36


def test_rotation_service_reads_persisted_policy(db_session, secret_store, versa_client):
    SettingsService(db_session).set_password_policy(PasswordPolicy(length=30))
    service = RotationService(db_session, secret_store, versa_client)
    assert service._policy.length == 30


def test_admin_policy_update_via_api_and_audit_event(app_client, db_session):
    from sqlalchemy import select

    from app.models.audit import AuditEvent

    resp = app_client.get("/api/v1/admin/password-policy")
    assert resp.status_code == 200
    assert resp.json()["length"] == 24

    body = {"length": 32, "min_lower": 2, "min_upper": 2, "min_digit": 2, "min_special": 2}
    resp = app_client.put("/api/v1/admin/password-policy", json=body)
    assert resp.status_code == 200
    assert resp.json()["length"] == 32

    events = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "PASSWORD_POLICY_UPDATED")
        )
    )
    assert len(events) == 1
    assert events[0].user_username == "admin"
    assert events[0].success is True
    import json

    meta = json.loads(events[0].metadata_json)
    assert meta["previous"]["length"] == 24
    assert meta["current"]["min_special"] == 2


def test_admin_policy_update_rejects_impossible_and_idempotent_put(app_client, db_session):
    from sqlalchemy import select

    from app.models.audit import AuditEvent

    # Impossible combination → 400 and no audit row.
    bad = {"length": 12, "min_lower": 6, "min_upper": 6, "min_digit": 2, "min_special": 1}
    resp = app_client.put("/api/v1/admin/password-policy", json=bad)
    assert resp.status_code == 400

    # No-op PUT → no audit row.
    default = {"length": 24, "min_lower": 1, "min_upper": 1, "min_digit": 1, "min_special": 1}
    resp = app_client.put("/api/v1/admin/password-policy", json=default)
    assert resp.status_code == 200

    events = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "PASSWORD_POLICY_UPDATED")
        )
    )
    assert len(events) == 0