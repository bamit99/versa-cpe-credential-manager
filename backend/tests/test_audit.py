from __future__ import annotations

from app.services.audit_service import AuditActions, AuditService


def test_audit_records_required_fields(db_session, admin_user):
    service = AuditService(db_session)
    corr = service.new_correlation_id()
    event = service.record(
        action=AuditActions.CREDENTIAL_VIEWED,
        user=admin_user,
        cpe_id="CPE-X",
        ticket_reference="INC-1",
        source_ip="10.0.0.5",
        correlation_id=corr,
    )
    assert event.user_username == "admin"
    assert event.cpe_id == "CPE-X"
    assert event.correlation_id == corr
    assert event.success is True


def test_audit_failure_flag(db_session, admin_user):
    service = AuditService(db_session)
    event = service.record(action=AuditActions.ACCESS_DENIED, user=admin_user, success=False)
    assert event.success is False


def test_no_secret_field_in_audit_schema(db_session):
    from app.models.audit import AuditEvent

    columns = {c.name for c in AuditEvent.__table__.columns}
    assert "secret" not in columns
    assert "password" not in columns


def test_secret_redaction_utility():
    from app.utils.crypto import redact_secrets

    text = '{"password": "hunter2", "client_secret": "abc123"} ok'
    cleaned = redact_secrets(text)
    assert "hunter2" not in cleaned
    assert "abc123" not in cleaned
    assert "***REDACTED***" in cleaned