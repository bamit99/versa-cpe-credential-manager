"""CPE inventory service (CRUD + CSV importer)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.keycloak import TokenUser
from app.config import get_settings
from app.models.access import CPEAssignment
from app.models.cpe import CPE, Director, User
from app.models.credential import Credential, CredentialStatus, RotationState
from app.services.audit_service import AuditActions, AuditService

_MAX_IMPORT_ROWS = 10_000


def _normalise_status(status: str | None) -> str:
    value = (status or "unknown").strip().lower()
    return value if value in {"online", "offline", "unknown"} else "unknown"


class CPEService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditService(db)

    def create(self, data: dict, director_id: int | None, user: TokenUser) -> CPE:
        if director_id is not None and not self._db.get(Director, director_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown director")
        cpe = CPE(
            cpe_id=data["cpe_id"],
            device_name=data.get("device_name"),
            serial_number=data.get("serial_number"),
            site=data.get("site"),
            management_ip=data.get("management_ip"),
            director_id=director_id,
            status=_normalise_status(data.get("status")),
        )
        self._db.add(cpe)
        self._db.commit()
        self._db.refresh(cpe)
        self._audit.record(
            action=AuditActions.CPE_UPDATED,  # noqa: on create use CPE_IMPORTED? keep CPE_IMPORTED for bulk
            user=user,
            cpe_id=cpe.cpe_id,
            metadata_json='{"operation":"create"}',
        )
        return cpe

    def update(self, cpe: CPE, data: dict, user: TokenUser) -> CPE:
        for field in (
            "device_name",
            "serial_number",
            "site",
            "management_ip",
            "director_id",
            "status",
            "last_seen_at",
            "is_active",
        ):
            if field in data and data[field] is not None:
                setattr(cpe, field, data[field])
        if "status" in data:
            cpe.status = _normalise_status(data["status"])
        self._db.commit()
        self._db.refresh(cpe)
        self._audit.record(
            action=AuditActions.CPE_UPDATED,
            user=user,
            cpe_id=cpe.cpe_id,
            metadata_json='{"operation":"update"}',
        )
        return cpe

    def get(self, cpe_id: str) -> CPE:
        row = self._db.scalar(select(CPE).where(CPE.cpe_id == cpe_id))
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPE not found")
        return row

    def list(
        self,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        site: str | None = None,
        director_id: int | None = None,
        needs_rotation: bool = False,
        sort_by: str = "cpe_id",
        sort_desc: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CPE], int]:
        stmt = select(CPE)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                CPE.cpe_id.ilike(like)
                | CPE.device_name.ilike(like)
                | CPE.serial_number.ilike(like)
                | CPE.site.ilike(like)
                | CPE.management_ip.ilike(like)
            )
        if status_filter:
            stmt = stmt.where(CPE.status == _normalise_status(status_filter))
        if site:
            stmt = stmt.where(CPE.site == site)
        if director_id is not None:
            stmt = stmt.where(CPE.director_id == director_id)
        if needs_rotation:
            stmt = stmt.join(Credential, Credential.cpe_id == CPE.id).where(
                Credential.status == CredentialStatus.ACTIVE.value,
                self._needs_rotation_condition(),
            )

        order_col = getattr(CPE, sort_by, CPE.cpe_id)
        stmt = stmt.order_by(order_col.desc() if sort_desc else order_col.asc())

        total = self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            self._db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        )
        return rows, int(total)

    @staticmethod
    def _needs_rotation_condition():
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=get_settings().rotation_due_days)
        return or_(
            Credential.rotation_state == RotationState.ROTATION_FAILED.value,
            Credential.next_rotation_at.isnot(None) & (Credential.next_rotation_at <= now),
            Credential.next_rotation_at.is_(None)
            & Credential.last_rotated_at.isnot(None)
            & (Credential.last_rotated_at <= cutoff),
            Credential.next_rotation_at.is_(None)
            & Credential.last_rotated_at.is_(None)
            & Credential.activated_at.isnot(None)
            & (Credential.activated_at <= cutoff),
        )

    def upsert_cpes(self, rows, user: TokenUser) -> tuple[int, int]:
        """Create-or-update CPE rows from discovery/import dicts. Returns (created, updated)."""
        created = updated = 0
        for i, row in enumerate(rows):
            if i >= _MAX_IMPORT_ROWS:
                break
            cpe_id = str(row.get("cpe_id") or "").strip()
            if not cpe_id:
                continue
            existing = self._db.scalar(select(CPE).where(CPE.cpe_id == cpe_id))
            if existing:
                self.update(existing, row, user)
                updated += 1
            else:
                self.create(row, None, user)
                created += 1
        return created, updated

    def import_csv(self, content: str, user: TokenUser) -> dict:
        reader = csv.DictReader(io.StringIO(content))
        expected = {"cpe_id", "device_name", "serial_number", "site", "management_ip"}
        if reader.fieldnames is None or not expected.intersection(reader.fieldnames):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must contain at least one of: {sorted(expected)}",
            )
        rows = [row for row in reader if (row.get("cpe_id") or "").strip()]
        created, updated = self.upsert_cpes(rows, user)
        self._audit.record(
            action=AuditActions.CPE_IMPORTED,
            user=user,
            metadata_json=f'{{"created":{created},"updated":{updated}}}',
        )
        return {"created": created, "updated": updated}


class AssignmentService:
    """MVP user-to-CPE assignment used for field-engineer authorisation."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def assign(self, user_subject: str, cpe_id: str, admin: TokenUser, audit: AuditService) -> None:
        if self._db.scalar(select(CPE).where(CPE.cpe_id == cpe_id)) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPE not found")
        existing = self._db.scalar(
            select(CPEAssignment).where(
                CPEAssignment.user_subject == user_subject,
                CPEAssignment.cpe_id == cpe_id,
            )
        )
        if existing is None:
            self._db.add(CPEAssignment(user_subject=user_subject, cpe_id=cpe_id))
            self._db.commit()
            audit.record(
                action=AuditActions.CPE_ASSIGNED,
                user=admin,
                cpe_id=cpe_id,
                metadata_json=f'{{"target_user":"{user_subject}"}}',
            )

    def is_assigned(self, user_subject: str, cpe_id: str) -> bool:
        return (
            self._db.scalar(
                select(CPEAssignment.id).where(
                    CPEAssignment.user_subject == user_subject,
                    CPEAssignment.cpe_id == cpe_id,
                )
            )
            is not None
        )

    def unassign(self, user_subject: str, cpe_id: str, admin: TokenUser, audit: AuditService) -> None:
        if self._db.scalar(select(CPE).where(CPE.cpe_id == cpe_id)) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPE not found")
        row = self._db.scalar(
            select(CPEAssignment).where(
                CPEAssignment.user_subject == user_subject,
                CPEAssignment.cpe_id == cpe_id,
            )
        )
        if row is None:
            return
        self._db.delete(row)
        self._db.commit()
        audit.record(
            action=AuditActions.CPE_UNASSIGNED,
            user=admin,
            cpe_id=cpe_id,
            metadata_json=f'{{"target_user":"{user_subject}"}}',
        )

    def list(self, user_subject: str | None = None) -> list[dict]:
        """Return assignment rows joined with user identity and device details."""
        stmt = (
            select(
                CPEAssignment,
                User.username,
                CPE.device_name,
                CPE.site,
            )
            .outerjoin(User, User.subject == CPEAssignment.user_subject)
            .outerjoin(CPE, CPE.cpe_id == CPEAssignment.cpe_id)
            .order_by(CPEAssignment.cpe_id)
        )
        if user_subject:
            stmt = stmt.where(CPEAssignment.user_subject == user_subject)
        out: list[dict] = []
        for assignment, username, device_name, site in self._db.execute(stmt).all():
            out.append(
                {
                    "user_subject": assignment.user_subject,
                    "username": username,
                    "cpe_id": assignment.cpe_id,
                    "device_name": device_name,
                    "site": site,
                    "assigned_at": assignment.created_at,
                }
            )
        return out