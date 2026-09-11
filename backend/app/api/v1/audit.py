"""Audit log endpoints (view-only; append-only storage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_security_operator
from app.db.session import get_db
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("", response_model=AuditLogResponse)
def list_audit(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
    action: str | None = Query(default=None),
    cpe_id: str | None = Query(default=None),
    user_subject: str | None = Query(default=None),
    success: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
) -> AuditLogResponse:
    service = AuditService(db)
    filters = {k: v for k, v in {
        "action": action, "cpe_id": cpe_id, "user_subject": user_subject, "success": success,
    }.items() if v is not None}
    items = service.list(limit=page_size, offset=(page - 1) * page_size, filters=filters)
    total = service.count(filters)
    return AuditLogResponse(items=items, total=total, page=page, page_size=page_size)