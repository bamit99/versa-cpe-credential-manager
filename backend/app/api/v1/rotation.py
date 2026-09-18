"""Rotation endpoints (single + bulk, bounded concurrency).

Bulk rotation runs CPEs through a thread pool with a hard concurrency cap and
a bounded batch size. Every CPE is rotated in its own DB session so workers
never share a session across threads. The client/secret-store factories are
dependency-injectable for tests.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.auth.keycloak import TokenUser, require_security_operator
from app.config import Settings, get_settings
from app.db.session import get_db, get_session_factory
from app.schemas.credential import CredentialOut
from app.services.cpe_service import CPEService
from app.services.rotation_service import RotationService
from app.services.secret_store.base import SecretStore, build_secret_store

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_CONCURRENT_ROTATIONS = 5
MAX_BULK_CPES = 100


def get_versa_client_factory():
    from app.adapters.versa.base import build_versa_client

    return build_versa_client


def get_secret_store_factory():
    return build_secret_store


@router.post("/cpes/{cpe_id}/rotate", response_model=CredentialOut)
def rotate_single(
    cpe_id: str,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
    settings: Settings = Depends(get_settings),
) -> CredentialOut:
    cpe = CPEService(db).get(cpe_id)
    store = build_secret_store(settings)
    client = get_versa_client_factory()(cpe.director, settings)
    return RotationService(db, store, client).request_rotation(cpe, user)


def _rotate_one(
    cpe_id: str,
    user: TokenUser,
    settings: Settings,
    session_factory: sessionmaker,
    store_factory,
    versa_factory,
) -> dict:
    """Rotate a single CPE inside its own session; always returns a result dict."""
    db: Session = session_factory()
    try:
        cpe = CPEService(db).get(cpe_id)
        store: SecretStore = store_factory(settings)
        client = versa_factory(cpe.director, settings)
        cred = RotationService(db, store, client).request_rotation(cpe, user)
        return {"cpe_id": cpe_id, "ok": True, "version": cred.version}
    except HTTPException as exc:
        return {"cpe_id": cpe_id, "ok": False, "error": exc.detail}
    except Exception as exc:  # noqa: BLE001 - worker boundary; report per-CPE, never fail the batch
        logger.exception("Unexpected error during rotation of %s", cpe_id)
        return {"cpe_id": cpe_id, "ok": False, "error": f"Unexpected error during rotation"}


@router.post("/bulk/rotate")
def rotate_bulk(
    cpe_ids: list[str],
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_security_operator),
    settings: Settings = Depends(get_settings),
    session_factory: sessionmaker = Depends(get_session_factory),
    store_factory=Depends(get_secret_store_factory),
    versa_factory=Depends(get_versa_client_factory),
):
    if len(cpe_ids) > MAX_BULK_CPES:
        raise HTTPException(status_code=400, detail=f"Bulk rotation is limited to {MAX_BULK_CPES} CPEs per request")
    if not cpe_ids:
        return {"requested": 0, "results": []}

    # De-duplicate while preserving order so the same CPE is never rotated twice in a batch.
    unique_ids = list(dict.fromkeys(cpe_ids))

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ROTATIONS) as pool:
        futures = {
            pool.submit(
                _rotate_one, cpe_id, user, settings, session_factory, store_factory, versa_factory
            ): cpe_id
            for cpe_id in unique_ids
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - worker already bounds its exceptions
                logger.exception("Bulk rotation task failed for %s", futures[future])
                results.append({"cpe_id": futures[future], "ok": False, "error": str(exc)})

    results.sort(key=lambda r: r["cpe_id"])
    return {"requested": len(unique_ids), "results": results}