"""Admin endpoints: directors, CPE assignments, credential generation policy."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, require_admin
from app.db.session import get_db
from app.models.cpe import Director
from app.models.credential import Credential
from app.schemas.cpe import AssignmentRequest, DirectorCreate, DirectorOut
from app.schemas.credential import CredentialOut, PasswordPolicyOut, PasswordPolicyUpdate
from app.services.audit_service import AuditService
from app.services.cpe_service import AssignmentService
from app.utils.crypto import PasswordPolicy

router = APIRouter()


@router.get("/directors", response_model=list[DirectorOut])
def list_directors(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> list[DirectorOut]:
    return list(db.scalars(select(Director)).all())


@router.post("/directors", response_model=DirectorOut, status_code=201)
def create_director(
    body: DirectorCreate,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> DirectorOut:
    director = Director(**body.model_dump())
    db.add(director)
    db.commit()
    db.refresh(director)
    return director


@router.delete("/directors/{director_id}", status_code=204)
def delete_director(
    director_id: int,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    director = db.get(Director, director_id)
    if director is None:
        raise HTTPException(status_code=404, detail="Director not found")
    db.delete(director)
    db.commit()


@router.post("/assignments", status_code=201)
def assign_cpe(
    body: AssignmentRequest,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    AssignmentService(db).assign(body.user_subject, body.cpe_id, user, AuditService(db))


@router.get("/credentials/{cpe_id}", response_model=list[CredentialOut])
def cpe_credentials(
    cpe_id: str,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    from app.models.cpe import CPE

    cpe = db.scalar(select(CPE).where(CPE.cpe_id == cpe_id))
    if cpe is None:
        raise HTTPException(status_code=404, detail="CPE not found")
    return list(
        db.scalars(select(Credential).where(Credential.cpe_id == cpe.id).order_by(Credential.version.desc()))
    )


@router.get("/password-policy", response_model=PasswordPolicyOut)
def get_policy(user: TokenUser = Depends(require_admin)):
    p = PasswordPolicy()
    return PasswordPolicyOut(
        length=p.length,
        min_lower=p.min_lower,
        min_upper=p.min_upper,
        min_digit=p.min_digit,
        min_special=p.min_special,
    )


@router.put("/password-policy", response_model=PasswordPolicyOut)
def update_policy(
    body: PasswordPolicyUpdate,
    user: TokenUser = Depends(require_admin),
):
    # Policy is global for MVP; persisted via settings/DB later. Validate constraints only.
    return PasswordPolicyOut(
        length=body.length,
        min_lower=body.min_lower,
        min_upper=body.min_upper,
        min_digit=body.min_digit,
        min_special=body.min_special,
    )