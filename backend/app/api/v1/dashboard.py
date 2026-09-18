"""Dashboard statistics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_security_operator
from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.cpe import CPE
from app.models.credential import Credential, CredentialStatus, RotationState
from app.schemas.audit import DashboardStats

router = APIRouter()


@router.get("", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
    settings: Settings = Depends(get_settings),
) -> DashboardStats:
    recent_days = datetime.now(timezone.utc) - timedelta(days=7)
    due_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.rotation_due_days)
    return DashboardStats(
        total_cpes=int(db.scalar(select(func.count()).select_from(CPE)) or 0),
        online_cpes=int(
            db.scalar(select(func.count()).select_from(CPE).where(CPE.status == "online")) or 0
        ),
        offline_cpes=int(
            db.scalar(select(func.count()).select_from(CPE).where(CPE.status == "offline")) or 0
        ),
        credentials_needing_rotation=int(
            db.scalar(
                select(func.count())
                .select_from(Credential)
                .where(
                    Credential.status == CredentialStatus.ACTIVE.value,
                    or_(
                        Credential.rotation_state == RotationState.ROTATION_FAILED.value,
                        Credential.next_rotation_at.isnot(None)
                        & (Credential.next_rotation_at <= datetime.now(timezone.utc)),
                        Credential.next_rotation_at.is_(None)
                        & Credential.last_rotated_at.isnot(None)
                        & (Credential.last_rotated_at <= due_cutoff),
                        Credential.next_rotation_at.is_(None)
                        & Credential.last_rotated_at.is_(None)
                        & Credential.activated_at.isnot(None)
                        & (Credential.activated_at <= due_cutoff),
                    ),
                )
            )
            or 0
        ),
        rotation_failures_recent=int(
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.action == "CREDENTIAL_ROTATION_FAILED",
                    AuditEvent.timestamp >= recent_days,
                )
            )
            or 0
        ),
        recent_privileged_access=int(
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.action == "CREDENTIAL_VIEWED",
                    AuditEvent.timestamp >= recent_days,
                )
            )
            or 0
        ),
        recent_rotations=int(
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.action == "CREDENTIAL_ROTATION_SUCCEEDED",
                    AuditEvent.timestamp >= recent_days,
                )
            )
            or 0
        ),
    )