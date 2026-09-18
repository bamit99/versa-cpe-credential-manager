"""CPE inventory endpoints (search, sort, filter, CSV import)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_admin, require_any_authenticated
from app.db.session import get_db
from app.schemas.cpe import (
    CPECreate,
    CPEListResponse,
    CPEOut,
    CPEUpdate,
    ImportResult,
)
from app.services.cpe_service import CPEService

router = APIRouter()


@router.get("", response_model=CPEListResponse)
def list_cpes(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_any_authenticated),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None, alias="status"),
    site: str | None = Query(default=None),
    director_id: int | None = Query(default=None),
    needs_rotation: bool = Query(default=False),
    sort_by: str = Query(default="cpe_id"),
    sort_desc: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> CPEListResponse:
    items, total = CPEService(db).list(
        search=search,
        status_filter=status,
        site=site,
        director_id=director_id,
        needs_rotation=needs_rotation,
        sort_by=sort_by,
        sort_desc=sort_desc,
        page=page,
        page_size=page_size,
    )
    return CPEListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{cpe_id}", response_model=CPEOut)
def get_cpe(
    cpe_id: str,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_any_authenticated),
) -> CPEOut:
    return CPEService(db).get(cpe_id)


@router.post("", response_model=CPEOut, status_code=201)
def create_cpe(
    body: CPECreate,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> CPEOut:
    return CPEService(db).create(body.model_dump(exclude_unset=True), body.director_id, user)


@router.patch("/{cpe_id}", response_model=CPEOut)
def update_cpe(
    cpe_id: str,
    body: CPEUpdate,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> CPEOut:
    service = CPEService(db)
    cpe = service.get(cpe_id)
    return service.update(cpe, body.model_dump(exclude_unset=True), user)


@router.post("/import", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> ImportResult:
    content = (await file.read()).decode("utf-8", errors="replace")
    return ImportResult(**CPEService(db).import_csv(content, user))