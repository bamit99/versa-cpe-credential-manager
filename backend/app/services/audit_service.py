"""Append-oriented audit logging. Never records secret material."""
from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.models.audit import AuditEvent


class AuditService:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def new_correlation_id() -> str:
        return str(uuid.uuid4())

    def record(
        self,
        *,
        action: str,
        user: TokenUser | None,
        cpe_id: str | None = None,
        ticket_reference: str | None = None,
        reason: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        correlation_id: str | None = None,
        metadata_json: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            user_subject=user.subject if user else None,
            user_username=user.username if user else None,
            user_role=",".join(user.roles) if user else None,
            action=action,
            cpe_id=cpe_id,
            ticket_reference=ticket_reference,
            reason=reason,
            source_ip=source_ip,
            user_agent=user_agent,
            success=success,
            correlation_id=correlation_id or self.new_correlation_id(),
            metadata_json=metadata_json,
        )
        self._db.add(event)
        self._db.commit()
        return event

    def list(self, *, limit: int = 100, offset: int = 0, filters: dict | None = None) -> list[AuditEvent]:
        filters = filters or {}
        stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc())
        if filters.get("action"):
            stmt = stmt.where(AuditEvent.action == filters["action"])
        if filters.get("cpe_id"):
            stmt = stmt.where(AuditEvent.cpe_id == filters["cpe_id"])
        if filters.get("user_subject"):
            stmt = stmt.where(AuditEvent.user_subject == filters["user_subject"])
        if filters.get("success") is not None:
            stmt = stmt.where(AuditEvent.success == filters["success"])
        return list(self._db.scalars(stmt.offset(offset).limit(limit)).all())

    def count(self, filters: dict | None = None) -> int:
        from sqlalchemy import func

        filters = filters or {}
        stmt = select(func.count(AuditEvent.id))
        if filters.get("action"):
            stmt = stmt.where(AuditEvent.action == filters["action"])
        return int(self._db.scalar(stmt) or 0)


class AuditActions:
    CREDENTIAL_VIEW_REQUESTED = "CREDENTIAL_VIEW_REQUESTED"
    CREDENTIAL_VIEWED = "CREDENTIAL_VIEWED"
    CREDENTIAL_GENERATED = "CREDENTIAL_GENERATED"
    CREDENTIAL_ROTATION_REQUESTED = "CREDENTIAL_ROTATION_REQUESTED"
    CREDENTIAL_ROTATION_STARTED = "CREDENTIAL_ROTATION_STARTED"
    CREDENTIAL_ROTATION_SUCCEEDED = "CREDENTIAL_ROTATION_SUCCEEDED"
    CREDENTIAL_ROTATION_FAILED = "CREDENTIAL_ROTATION_FAILED"
    CPE_IMPORTED = "CPE_IMPORTED"
    CPE_DISCOVERED = "CPE_DISCOVERED"
    CPE_UPDATED = "CPE_UPDATED"
    CPE_ASSIGNED = "CPE_ASSIGNED"
    CPE_UNASSIGNED = "CPE_UNASSIGNED"
    IDENTITY_SYNCED = "IDENTITY_SYNCED"
    PASSWORD_POLICY_UPDATED = "PASSWORD_POLICY_UPDATED"
    ACCESS_DENIED = "ACCESS_DENIED"
    LOGIN = "LOGIN"