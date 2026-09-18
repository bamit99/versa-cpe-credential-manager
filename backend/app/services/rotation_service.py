"""Credential rotation state machine.

Critical rule: if push/verification fails, the old active credential is
NEVER replaced. The rotation is marked FAILED and the previous reference
retains its ACTIVE status.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.config import get_settings
from app.models.cpe import CPE
from app.models.credential import Credential, CredentialStatus, RotationState
from app.adapters.versa.base import VersaClient
from app.services.audit_service import AuditActions, AuditService
from app.services.credential_service import CredentialService
from app.services.secret_store.base import SecretNotFoundError, SecretStore
from app.services.settings_service import SettingsService
from app.utils.crypto import PasswordPolicy, generate_password

logger = logging.getLogger(__name__)

# States where a rotation is actively in flight — a new request must be rejected.
_ACTIVE_ROTATION_STATES = {
    RotationState.ROTATION_REQUESTED.value,
    RotationState.NEW_SECRET_GENERATED.value,
    RotationState.PUSH_TO_CPE.value,
    RotationState.VERIFY_NEW.value,
}


class RotationError(Exception):
    pass


class RotationService:
    def __init__(
        self,
        db: Session,
        store: SecretStore,
        versa_client: VersaClient,
        password_policy: PasswordPolicy | None = None,
        rotation_interval_days: int | None = None,
    ) -> None:
        self._db = db
        self._store = store
        self._versa = versa_client
        self._audit = AuditService(db)
        self._policy = password_policy if password_policy is not None else SettingsService(db).get_password_policy()
        self._rotation_interval_days = (
            rotation_interval_days if rotation_interval_days is not None else get_settings().rotation_interval_days
        )

    def request_rotation(self, cpe: CPE, user: TokenUser) -> Credential:
        cred = self._db.scalar(
            select(Credential).where(
                Credential.cpe_id == cpe.id,
                Credential.status == CredentialStatus.ACTIVE.value,
            ).order_by(Credential.version.desc()).limit(1)
        )
        if cred is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active credential to rotate")
        if cred.rotation_state in _ACTIVE_ROTATION_STATES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A rotation is already in progress (state: {cred.rotation_state})",
            )

        self._audit.record(
            action=AuditActions.CREDENTIAL_ROTATION_REQUESTED,
            user=user,
            cpe_id=cpe.cpe_id,
        )

        # Transition: ROTATION_REQUESTED
        cred.rotation_state = RotationState.ROTATION_REQUESTED.value
        self._db.commit()

        return self._execute_rotation(cpe, cred, user)

    def _execute_rotation(self, cpe: CPE, cred: Credential, user: TokenUser) -> Credential:
        # Transition: NEW_SECRET_GENERATED
        cred.rotation_state = RotationState.NEW_SECRET_GENERATED.value
        self._db.commit()

        new_reference = CredentialService.new_reference()
        new_secret = generate_password(self._policy)
        self._store.create_secret(new_reference, new_secret)

        # Transition: PUSH_TO_CPE
        cred.rotation_state = RotationState.PUSH_TO_CPE.value
        self._db.commit()
        self._audit.record(
            action=AuditActions.CREDENTIAL_ROTATION_STARTED,
            user=user,
            cpe_id=cpe.cpe_id,
        )

        push_ok = self._versa.update_credential(cpe, new_secret)
        if not push_ok:
            return self._fail_rotation(cpe, cred, user, new_reference, new_secret, "Push to CPE failed")

        # Transition: VERIFY_NEW
        cred.rotation_state = RotationState.VERIFY_NEW.value
        self._db.commit()

        verify_ok = self._versa.verify_credential(cpe, new_secret)
        if not verify_ok:
            return self._fail_rotation(cpe, cred, user, new_reference, new_secret, "Credential verification failed")

        # Transition: NEW_SECRET_ACTIVE — old reference stays, old value in SecretStore retained.
        # Snapshot the current row as immutable RETIRED history BEFORE mutating it.
        self._db.add(
            Credential(
                cpe_id=cred.cpe_id,
                username=cred.username,
                secret_reference=cred.secret_reference,
                version=cred.version,
                status=CredentialStatus.RETIRED.value,
                rotation_state=RotationState.OLD_SECRET_RETIRED.value,
                created_at=cred.created_at,
                activated_at=cred.activated_at,
                retired_at=datetime.now(timezone.utc),
                last_accessed_at=cred.last_accessed_at,
                last_rotated_at=cred.last_rotated_at,
                next_rotation_at=cred.next_rotation_at,
            )
        )
        cred.rotation_state = RotationState.NEW_SECRET_ACTIVE.value
        cred.status = CredentialStatus.ACTIVE.value
        cred.secret_reference = new_reference
        cred.version += 1
        now = datetime.now(timezone.utc)
        cred.activated_at = now
        cred.last_rotated_at = now
        cred.next_rotation_at = now + timedelta(days=self._rotation_interval_days)
        self._db.commit()

        # Retire the old reference
        cred.rotation_state = RotationState.OLD_SECRET_RETIRED.value
        self._db.commit()

        self._audit.record(
            action=AuditActions.CREDENTIAL_ROTATION_SUCCEEDED,
            user=user,
            cpe_id=cpe.cpe_id,
            metadata_json=f'{{"version":{cred.version}}}',
        )
        return cred

    def _fail_rotation(
        self,
        cpe: CPE,
        cred: Credential,
        user: TokenUser,
        new_reference: str,
        new_secret: str,
        detail: str,
    ) -> Credential:
        """On failure, the ACTIVE reference is preserved. New material is deleted."""
        cred.rotation_state = RotationState.ROTATION_FAILED.value
        self._db.commit()

        # Remove the newly generated (never used) secret from the store.
        try:
            self._store.delete_secret(new_reference)
        except SecretNotFoundError:
            pass

        self._audit.record(
            action=AuditActions.CREDENTIAL_ROTATION_FAILED,
            user=user,
            cpe_id=cpe.cpe_id,
            success=False,
            metadata_json=f'{{"reason":"{detail}"}}',
        )

        logger.warning("Rotation failed for %s: %s", cpe.cpe_id, detail)
        # The ACTIVE credential remains untouched.
        return cred