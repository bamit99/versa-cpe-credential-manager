"""Rotation endpoints (single + bulk, bounded concurrency)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_security_operator
from app.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.credential import CredentialOut
from app.services.cpe_service import CPEService
from app.services.rotation_service import RotationService
from app.services.secret_store.base import build_secret_store

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_CONCURRENT_ROTATIONS = 5


@router.post("/cpes/{cpe_id}/rotate", response_model=CredentialOut)
def rotate_single(
    cpe_id: str,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
    settings: Settings = Depends(get_settings),
) -> CredentialOut:
    cpe = CPEService(db).get(cpe_id)
    service = RotationService(db, build_secret_store(settings), build_versa_client_for(cpe, settings))
    return service.request_rotation(cpe, user)


@router.post("/bulk/rotate")
def rotate_bulk(
    cpe_ids: list[str],
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
    settings: Settings = Depends(get_settings),
):
    from app.adapters.versa.base import build_versa_client

    results: list[dict] = []
    for cpe_id in cpe_ids:
        try:
            cpe = CPEService(db).get(cpe_id)
            service = RotationService(db, build_secret_store(settings), build_versa_client(cpe.director, settings))
            cred = service.request_rotation(cpe, user)
            results.append({"cpe_id": cpe_id, "ok": True, "version": cred.version})
        except HTTPException as exc:
            results.append({"cpe_id": cpe_id, "ok": False, "error": exc.detail})
    return {"requested": len(cpe_ids), "results": results}


def build_versa_client_for(cpe, settings):
    from app.adapters.versa.base import build_versa_client
    return build_versa_client(cpe.director, settings)