"""Current-user profile & assignment listing (registers identity on first call)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser, get_current_user
from app.db.session import get_db
from app.models.access import CPEAssignment
from app.models.cpe import CPE, User

router = APIRouter()


def _upsert_user(db: Session, user: TokenUser) -> User:
    roles_json = json.dumps(user.roles)
    row = db.scalar(select(User).where(User.subject == user.subject))
    if row is None:
        row = User(
            subject=user.subject,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=roles_json,
        )
        db.add(row)
    else:
        row.username = user.username
        row.email = user.email
        row.roles = roles_json
    db.commit()
    db.refresh(row)
    return row


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    db_user = _upsert_user(db, user)
    assigned = list(
        db.scalars(
            select(CPE).join(CPEAssignment, CPE.cpe_id == CPEAssignment.cpe_id).filter(
                CPEAssignment.user_subject == user.subject,
                CPE.is_active.is_(True),
            )
        ).all()
    )
    return {
        "subject": user.subject,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "roles": user.roles,
        "assigned_cpes": [c.cpe_id for c in assigned],
    }