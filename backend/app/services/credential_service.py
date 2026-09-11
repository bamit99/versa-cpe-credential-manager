"""Credential storage service.

The credential VALUE is only ever written to / read from the SecretStore.
The database row holds username + secret_reference + lifecycle metadata.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.models.cpe import CPE
from app.models.credential import Credential, CredentialStatus
from app.services.audit_service import AuditActions, AuditService
from app.services.cpe_service import AssignmentService
from app.services.secret_store.base import SecretStore
from app.utils.crypto import PasswordPolicy, generate_password


class CredentialService:
    def __init__(self, db: Session, store: SecretStore, password_policy: PasswordPolicy | None = None) -> None:
        self._db = db
        self._store = store
        self._policy = password_policy or PasswordPolicy()
        self._audit = AuditService(db)

    def new_reference(self) -> str:
        return f"cred:{uuid.uuid4().hex}"

    def create_for_cpe(self, cpe: CPE, username: str, user: TokenUser) -> Credential:
        reference = self.new_reference()
        secret = generate_password(self._policy)
        self._store.create_secret(reference, secret)
        cred = Credential(
            cpe_id=cpe.id,
            username=username,
            secret_reference=reference,
            version=1,
            status=CredentialStatus.ACTIVE.value,
            activated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active credential")

        secret = self._store.get_secret(cred.secret_reference)
        if secret is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Secret store miss")

        cred.last_accessed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
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
        return cred, secret, correlation_id