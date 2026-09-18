from __future__ import annotations

from sqlalchemy import select

from app.models.access import AccessRequest
from app.models.cpe import User
from app.services.audit_service import AuditService
from app.services.cpe_service import AssignmentService
from app.services.credential_service import CredentialService


def _assign(db_session, admin_user, cpe_id="CPE-TEST-0001"):
    AssignmentService(db_session).assign("sub-field", cpe_id, admin_user, AuditService(db_session))


def _active_credential_rows(db_session):
    return list(db_session.scalars(select(AccessRequest)).all())


def test_granted_reveal_persists_access_request(
    db_session, secret_store, sample_cpe, field_user, admin_user
):
    _assign(db_session, admin_user)
    CredentialService(db_session, secret_store).create_for_cpe(sample_cpe, "admin", admin_user)
    service = CredentialService(db_session, secret_store)
    _, _, correlation_id = service.get_with_secret(
        sample_cpe,
        field_user,
        reason="Subscriber firewall fault",
        ticket_reference="INC-88",
        assignments=AssignmentService(db_session),
        display_timeout_seconds=300,
    )

    rows = _active_credential_rows(db_session)
    assert len(rows) == 1
    req = rows[0]
    assert req.status == "granted"
    assert req.correlation_id == correlation_id
    assert req.reason == "Subscriber firewall fault"
    assert req.ticket_reference == "INC-88"
    assert req.granted_at is not None
    assert req.expires_at is not None
    # expires_at ≈ granted_at + display timeout
    delta = (req.expires_at - req.granted_at).total_seconds()
    assert abs(delta - 300) < 1
    # The requester identity is mirrored into users.
    assert db_session.scalar(select(User).where(User.subject == "sub-field")) is not None


def test_denied_reveal_persists_denied_access_request(
    db_session, secret_store, sample_cpe, field_user, admin_user
):
    # field_user is NOT assigned -> reveal must fail and leave a denied request.
    service = CredentialService(db_session, secret_store)
    try:
        service.get_with_secret(
            sample_cpe,
            field_user,
            reason="Not my device",
            assignments=AssignmentService(db_session),
        )
        raise AssertionError("expected HTTPException")
    except Exception:
        pass

    rows = _active_credential_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == "denied"
    assert rows[0].granted_at is None
    assert rows[0].expires_at is None


def test_admin_reveal_without_request_records_no_access_request(
    db_session, secret_store, sample_cpe, admin_user
):
    # Privileged reveal without a reason/ticket is not a "request" -> no row.
    CredentialService(db_session, secret_store).create_for_cpe(sample_cpe, "admin", admin_user)
    service = CredentialService(db_session, secret_store)
    service.get_with_secret(
        sample_cpe,
        admin_user,
        assignments=AssignmentService(db_session),
    )
    assert _active_credential_rows(db_session) == []


def test_admin_reveal_with_reason_records_access_request(
    db_session, secret_store, sample_cpe, admin_user
):
    CredentialService(db_session, secret_store).create_for_cpe(sample_cpe, "admin", admin_user)
    service = CredentialService(db_session, secret_store)
    service.get_with_secret(
        sample_cpe,
        admin_user,
        reason="Verification run",
        assignments=AssignmentService(db_session),
    )
    rows = _active_credential_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == "granted"