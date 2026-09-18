"""Identity mirror: upsert the authenticated Keycloak identity into `users`."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.models.cpe import User


def upsert_user(db: Session, user: TokenUser) -> User:
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