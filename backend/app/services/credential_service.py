"""Credential storage service.

The credential VALUE is only ever written to / read from the SecretStore.
The database row holds username + secret_reference + lifecycle metadata.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.config import get_settings
from app.models.access import AccessRequest
from app.models.cpe import CPE, User
from app.models.credential import Credential, CredentialStatus
from app.services.audit_service import AuditActions, AuditService
from app.services.cpe_service import AssignmentService
from app.services.secret_store.base import SecretStore
from app.services.settings_service import SettingsService
from app.services.user_service import upsert_user
from app.utils.crypto import PasswordPolicy, generate_password


class CredentialService:
    def __init__(
        self,
        db: Session,
        store: SecretStore,
        password_policy: PasswordPolicy | None = None,
        rotation_interval_days: int | None = None,
    ) -> None:
        self._db = db
        self._store = store
        self._policy = password_policy if password_policy is not None else SettingsService(db).get_password_policy()
        self._rotation_interval_days = (
            rotation_interval_days if rotation_interval_days is not None else get_settings().rotation_interval_days
        )
        self._audit = AuditService(db)

    @staticmethod
    def new_reference() -> str:
        return f"cred:{uuid.uuid4().hex}"

    def create_for_cpe(self, cpe: CPE, username: str, user: TokenUser) -> Credential:
        reference = self.new_reference()
        secret = generate_password(self._policy)
        self._store.create_secret(reference, secret)
        activated_at = datetime.now(timezone.utc)
        cred = Credential(
            cpe_id=cpe.id,
            username=username,
            secret_reference=reference,
            version=1,
            status=CredentialStatus.ACTIVE.value,
            activated_at=activated_at,
            next_rotation_at=activated_at + timedelta(days=self._rotation_interval_days),
        )
        self._db.add(cred)
        self._db.commit()
        self._db.refresh(cred)
        self._audit.record(
            action=AuditActions.CREDENTIAL_GENERATED,
            user=user,
            cpe_id=cpe.cpe_id,
        )
        return cred

    def active_credential(self, cpe: CPE) -> Credential | None:
        return self._db.scalar(
            select(Credential)
            .where(
                Credential.cpe_id == cpe.id,
                Credential.status == CredentialStatus.ACTIVE.value,
            )
            .order_by(Credential.version.desc())
            .limit(1)
        )

    def _record_access_request(
        self,
        cpe: CPE,
        user: TokenUser,
        *,
        reason: str | None,
        ticket_reference: str | None,
        correlation_id: str,
        granted: bool,
        display_timeout_seconds: int,
    ) -> None:
        """Persist a field-engineer retrieval request (granted or denied).

        Only recorded when the requester supplied a reason and/or ticket;
        direct admin/operator reveals without a request are audited only.
        """
        if not (reason or ticket_reference):
            return
        db_user: User = upsert_user(self._db, user)
        now = datetime.now(timezone.utc)
        self._db.add(
            AccessRequest(
                user_id=db_user.id,
                cpe_id=cpe.id,
                reason=reason or "",
                ticket_reference=ticket_reference,
                status="granted" if granted else "denied",
                correlation_id=correlation_id,
                requested_at=now,
                granted_at=now if granted else None,
                expires_at=datetime.fromtimestamp(
                    now.timestamp() + display_timeout_seconds, tz=timezone.utc
                )
                if granted
                else None,
            )
        )
        self._db.commit()

    def get_with_secret(
        self,
        cpe: CPE,
        user: TokenUser,
        *,
        reason: str | None = None,
        ticket_reference: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        assignments: AssignmentService,
        display_timeout_seconds: int = 180,
    ) -> tuple[Credential, str, str]:
        """Authorised credential retrieval for field engineers.

        Enforces assignment gate, records access audit events, and returns the
        secret value. The value is NOT cached anywhere in the app.
        """
        if user.has_role("field_engineer") and not assignments.is_assigned(user.subject, cpe.cpe_id):
            corr = self._audit.record(
                action=AuditActions.ACCESS_DENIED,
                user=user,
                cpe_id=cpe.cpe_id,
                reason=reason,
                source_ip=source_ip,
                user_agent=user_agent,
                success=False,
            )
            self._record_access_request(
                cpe, user, reason=reason, ticket_reference=ticket_reference,
                correlation_id=corr.correlation_id, granted=False,
                display_timeout_seconds=display_timeout_seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorised for this CPE",
                headers={"X-Correlation-ID": corr.correlation_id},
            )

        if user.has_role("field_engineer") and not (reason or ticket_reference):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A reason and/or ticket reference is required",
            )

        correlation_id = self._audit.record(
            action=AuditActions.CREDENTIAL_VIEW_REQUESTED,
            user=user,
            cpe_id=cpe.cpe_id,
            ticket_reference=ticket_reference,
            reason=reason,
            source_ip=source_ip,
            user_agent=user_agent,
        ).correlation_id

        cred = self.active_credential(cpe)
        if cred is None:
            self._audit.record(
                action=AuditActions.ACCESS_DENIED,
                user=user,
                cpe_id=cpe.cpe_id,
                success=False,
                correlation_id=correlation_id,
            )
            self._record_access_request(
                cpe, user, reason=reason, ticket_reference=ticket_reference,
                correlation_id=correlation_id, granted=False,
                display_timeout_seconds=display_timeout_seconds,
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active credential")

        secret = self._store.get_secret(cred.secret_reference)
        if secret is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Secret store miss")

        cred.last_accessed_at = datetime.now(timezone.utc)
        self._db.commit()

        self._audit.record(
            action=AuditActions.CREDENTIAL_VIEWED,
            user=user,
            cpe_id=cpe.cpe_id,
            ticket_reference=ticket_reference,
            reason=reason,
            source_ip=source_ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
        self._record_access_request(
            cpe, user, reason=reason, ticket_reference=ticket_reference,
            correlation_id=correlation_id, granted=True,
            display_timeout_seconds=display_timeout_seconds,
        )
        return cred, secret, correlation_id