"""Admin endpoints: directors, CPE assignments, credential generation policy."""
from __future__ import annotations

import json
import socket
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.rotation import get_secret_store_factory, get_versa_client_factory
from app.auth.keycloak import TokenUser, require_admin
from app.config import get_settings
from app.db.session import get_db
from app.models.cpe import Director
from app.models.credential import Credential
from app.schemas.cpe import (
    AssignmentOut,
    AssignmentRequest,
    DirectorCreate,
    DirectorOut,
    DirectorStatusOut,
    DirectorUpdate,
    SyncCpesResult,
    UserOut,
)
from app.schemas.credential import CredentialOut, PasswordPolicyOut, PasswordPolicyUpdate
from app.schemas.integration import IntegrationStatusOut
from app.services.audit_service import AuditActions, AuditService
from app.services.cpe_service import AssignmentService, CPEService
from app.services.integration_service import IntegrationStatusService
from app.services.settings_service import SettingsService
from app.utils.crypto import PasswordPolicy, policy_to_dict

router = APIRouter()


def _director_out(director: Director) -> DirectorOut:
    try:
        capabilities = json.loads(director.capabilities_json or "{}")
        if not isinstance(capabilities, dict):
            capabilities = {}
    except ValueError:
        capabilities = {}
    return DirectorOut(
        id=director.id,
        name=director.name,
        host=director.host,
        api_base_url=director.api_base_url,
        versa_version=director.versa_version,
        enabled=director.enabled,
        capabilities={str(k): bool(v) for k, v in capabilities.items()},
        created_at=director.created_at,
    )


@router.get("/directors", response_model=list[DirectorOut])
def list_directors(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> list[DirectorOut]:
    return [_director_out(d) for d in db.scalars(select(Director)).all()]


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
    return _director_out(director)


@router.put("/directors/{director_id}", response_model=DirectorOut)
def update_director(
    director_id: int,
    body: DirectorUpdate,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> DirectorOut:
    director = db.get(Director, director_id)
    if director is None:
        raise HTTPException(status_code=404, detail="Director not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(director, field, value)
    db.commit()
    db.refresh(director)
    return _director_out(director)


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


@router.get("/directors/{director_id}/status", response_model=DirectorStatusOut)
def director_status(
    director_id: int,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> DirectorStatusOut:
    from urllib.parse import urlparse

    director = db.get(Director, director_id)
    if director is None:
        raise HTTPException(status_code=404, detail="Director not found")
    parsed = urlparse(director.api_base_url)
    host = parsed.hostname or director.host
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=3):
            latency_ms = int((time.perf_counter() - start) * 1000)
        return DirectorStatusOut(reachable=True, detail="TCP reachable", latency_ms=latency_ms)
    except OSError as exc:
        return DirectorStatusOut(reachable=False, detail=str(exc))


@router.post("/directors/{director_id}/sync-cpes", response_model=SyncCpesResult)
def sync_cpes(
    director_id: int,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
    settings=Depends(get_settings),
    store_factory=Depends(get_secret_store_factory),
    versa_factory=Depends(get_versa_client_factory),
) -> SyncCpesResult:
    """Pull the Director's discovered CPE inventory into the local inventory."""
    from app.schemas.cpe import SyncCpesResult

    director = db.get(Director, director_id)
    if director is None:
        raise HTTPException(status_code=404, detail="Director not found")
    store = store_factory(settings)
    client = versa_factory(director, settings, store)
    try:
        devices = client.discover_devices(director)
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    created, updated = CPEService(db).upsert_cpes(devices, user)
    AuditService(db).record(
        action=AuditActions.CPE_DISCOVERED,
        user=user,
        metadata_json=json.dumps(
            {"director": director.name, "discovered": len(devices), "created": created, "updated": updated}
        ),
    )
    return SyncCpesResult(discovered=len(devices), created=created, updated=updated)


@router.post("/assignments", status_code=201)
def assign_cpe(
    body: AssignmentRequest,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    AssignmentService(db).assign(body.user_subject, body.cpe_id, user, AuditService(db))


@router.delete("/assignments")
def unassign_cpe(
    body: AssignmentRequest,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    AssignmentService(db).unassign(body.user_subject, body.cpe_id, user, AuditService(db))


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(
    user_subject: str | None = None,
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> list[AssignmentOut]:
    rows = AssignmentService(db).list(user_subject=user_subject)
    return [AssignmentOut(**row) for row in rows]


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> list[UserOut]:
    from app.models.cpe import User
    from app.auth.keycloak import parse_roles_json

    users = db.scalars(select(User).order_by(User.username)).all()
    return [
        UserOut(
            subject=u.subject,
            username=u.username,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            roles=parse_roles_json(u.roles),
            enabled=u.enabled,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.post("/sync/users")
def sync_users(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
) -> dict:
    from app.services.identity_sync_service import IdentitySyncError, IdentitySyncService

    try:
        return IdentitySyncService(db).sync(user)
    except IdentitySyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def get_integration_service(
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> IntegrationStatusService:
    return IntegrationStatusService(db, settings=settings)


@router.get("/integrations", response_model=IntegrationStatusOut)
def integrations_status(
    user: TokenUser = Depends(require_admin),
    service: IntegrationStatusService = Depends(get_integration_service),
) -> IntegrationStatusOut:
    """Read-only status of the external integrations this tool depends on."""
    return service.collect()


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
def get_policy(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    p = SettingsService(db).get_password_policy()
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
    db: Session = Depends(get_db),
    user: TokenUser = Depends(require_admin),
):
    policy = PasswordPolicy(
        length=body.length,
        min_lower=body.min_lower,
        min_upper=body.min_upper,
        min_digit=body.min_digit,
        min_special=body.min_special,
    )
    settings = SettingsService(db)
    previous = settings.get_password_policy()
    try:
        settings.set_password_policy(policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if policy_to_dict(previous) != policy_to_dict(policy):
        AuditService(db).record(
            action=AuditActions.PASSWORD_POLICY_UPDATED,
            user=user,
            metadata_json=json.dumps(
                {"previous": policy_to_dict(previous), "current": policy_to_dict(policy)}
            ),
        )
    return PasswordPolicyOut(
        length=policy.length,
        min_lower=policy.min_lower,
        min_upper=policy.min_upper,
        min_digit=policy.min_digit,
        min_special=policy.min_special,
    )