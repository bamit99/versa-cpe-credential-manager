"""Dashboard statistics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_security_operator
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.cpe import CPE
from app.models.credential import Credential
from app.schemas.audit import DashboardStats

router = APIRouter()


@router.get("", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
) -> DashboardStats:
    recent_days = datetime.now(timezone.utc) - timedelta(days=7)
    return DashboardStats(
        total_cpes=int(db.scalar(select(func.count()).select_from(CPE)) or 0),
        online_cpes=int(
            db.scalar(select(func.count()).select_from(CPE).where(CPE.status == "online")) or 0
        ),
        offline_cpes=int(
            db.scalar(select(func.count()).select_from(CPE).where(CPE.status == "offline")) or 0
        ),
        credentials_needing_rotation=int(db.scalar(select(func.count()).select_from(Credential)) or 0),
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