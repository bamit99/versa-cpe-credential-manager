from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.credential import Credential
from app.services.audit_service import AuditService
from app.services.cpe_service import AssignmentService, CPEService
from app.services.credential_service import CredentialService


@pytest.fixture()
def cred_service(db_session, secret_store):
    return CredentialService(db_session, secret_store)


@pytest.fixture()
def assignment_service(db_session):
    return AssignmentService(db_session)


def _assign(admin_user, assignment_service, cpe_id="CPE-TEST-0001", db_session=None):
    assignment_service.assign("sub-field", cpe_id, admin_user, AuditService(db_session))


def test_create_credential_write_secret_only_reference(db_session, secret_store, sample_cpe, admin_user):
    service = CredentialService(db_session, secret_store)
    cred = service.create_for_cpe(sample_cpe, "admin", admin_user)
    assert cred.secret_reference.startswith("cred:")
    # DB row does not hold the secret.
    assert "secret_reference" in [c.name for c in Credential.__table__.columns]
    assert "password" not in [c.name for c in Credential.__table__.columns]
    # The secret exists only in the store.
    assert secret_store.get_secret(cred.secret_reference) is not None


def test_field_engineer_requires_authorisation_governance(
    cred_service, db_session, secret_store, sample_cpe, field_user, admin_user, assignment_service
):
    cpe = sample_cpe
    with pytest.raises(HTTPException) as exc:
        cred_service.get_with_secret(
            cpe, field_user, source_ip="1.2.3.4", assignments=assignment_service
        )
    assert exc.value.status_code == 403  # not assigned

    _assign(admin_user, assignment_service, cpe.cpe_id, db_session)
    with pytest.raises(HTTPException) as exc:
        cred_service.get_with_secret(
            cpe, field_user, source_ip="1.2.3.4", assignments=assignment_service
        )
    assert exc.value.status_code == 400  # assigned but no reason/ticket


def test_assigned_field_engineer_can_reveal(
    cred_service, db_session, secret_store, sample_cpe, field_user, admin_user, assignment_service
):
    cpe = sample_cpe
    _assign(admin_user, assignment_service, cpe.cpe_id, db_session)
    cred = cred_service.create_for_cpe(cpe, "admin", admin_user)
    result = cred_service.get_with_secret(
        cpe,
        field_user,
        reason="On-site troubleshooting",
        ticket_reference="INC-42",
        source_ip="1.2.3.4",
        assignments=assignment_service,
    )
    cred_out, secret, correlation_id = result
    assert secret == secret_store.get_secret(cred.secret_reference)
    assert correlation_id
    # Audit trail exists.
    events = AuditService(db_session).list()
    actions = {e.action for e in events}
    assert "CREDENTIAL_VIEW_REQUESTED" in actions
    assert "CREDENTIAL_VIEWED" in actions


def test_audit_never_contains_secret_value(
    cred_service, db_session, secret_store, sample_cpe, field_user, admin_user, assignment_service
):
    cpe = sample_cpe
    _assign(admin_user, assignment_service, cpe.cpe_id, db_session)
    cred = cred_service.create_for_cpe(cpe, "admin", admin_user)
    secret_value = secret_store.get_secret(cred.secret_reference)
    _ = cred_service.get_with_secret(
        cpe, field_user, reason="test", assignments=assignment_service
    )
    for event in AuditService(db_session).list():
        for field in ("reason", "ticket_reference", "metadata_json", "user_role", "action"):
            raw = getattr(event, field, None) or ""
            assert secret_value not in raw