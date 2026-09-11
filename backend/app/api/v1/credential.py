"""Credential access endpoints (authorised reveal)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_any_authenticated
from app.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.credential import AccessRequestCreate, CredentialRevealResponse
from app.services.credential_service import CredentialService
from app.services.cpe_service import AssignmentService, CPEService
from app.services.secret_store.base import build_secret_store

logger = logging.getLogger(__name__)

router = APIRouter()


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()
    return ip, request.headers.get("user-agent")


@router.post(
    "/cpes/{cpe_id}/reveal",
    response_model=CredentialRevealResponse,
    summary="Temporarily reveal the active credential for an authorised CPE",
)
def reveal_credential(
    cpe_id: str,
    body: AccessRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_any_authenticated),
    settings: Settings = Depends(get_settings),
) -> CredentialRevealResponse:
    cpe = CPEService(db).get(cpe_id)
    store = build_secret_store(settings)
    service = CredentialService(db, store)
    source_ip, user_agent = _client_context(request)
    cred, secret, correlation_id = service.get_with_secret(
        cpe,
        user,
        reason=body.reason,
        ticket_reference=body.ticket_reference,
        source_ip=source_ip,
        user_agent=user_agent,
        assignments=AssignmentService(db),
    )
    return CredentialRevealResponse(
        username=cred.username,
        password=secret,
        version=cred.version,
        correlation_id=correlation_id,
        display_timeout_seconds=settings.credential_display_timeout_seconds,
    )


@router.get("/cpes/{cpe_id}/credential", summary="Credential metadata (NEVER the secret)")
def credential_metadata(
    cpe_id: str,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_any_authenticated),
):
    from app.models.credential import Credential

    cpe = CPEService(db).get(cpe_id)
    cred = db.query(Credential).filter(
        Credential.cpe_id == cpe.id, Credential.status == "ACTIVE"
    ).order_by(Credential.version.desc()).first()
    if cred is None:
        return JSONResponse({"username": None, "version": None}, status_code=404)
    return {
        "username": cred.username,
        "version": cred.version,
        "status": cred.status,
        "last_accessed_at": cred.last_accessed_at,
        "last_rotated_at": cred.last_rotated_at,
    }