"""Demo data seed (idempotent). Run after migrations:
    python -m app.seed
Creates demo Directors, CPEs, credentials and field-engineer assignments.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.access import CPEAssignment
from app.models.cpe import CPE, Director
from app.models.credential import Credential
from app.services.credential_service import CredentialService
from app.services.secret_store.base import build_secret_store
from app.utils.crypto import PasswordPolicy

logger = logging.getLogger(__name__)

DEMO_DIRECTORS = [
    {"name": "VD-LABS-2213", "host": "director-2213.example.com", "api_base_url": "https://director-2213.example.com:9183", "versa_version": "22.1.3", "oauth_client_id": "versa-cpe-manager"},
    {"name": "VD-LABS-2214", "host": "director-2214.example.com", "api_base_url": "https://director-2214.example.com:9183", "versa_version": "22.1.4", "oauth_client_id": "versa-cpe-manager"},
]

DEMO_CPES = [
    # (cpe_id, device_name, serial, site, ip, director_index, status)
    ("CPE-2213-0001", "BR-EDGE-MUM-01", "VS-2213-00000001", "Mumbai DC", "10.10.1.11", 0, "online"),
    ("CPE-2213-0002", "BR-EDGE-DEL-01", "VS-2213-00000002", "Delhi DC", "10.10.2.11", 0, "online"),
    ("CPE-2213-0003", "BR-EDGE-BLR-01", "VS-2213-00000003", "Bengaluru DC", "10.10.3.11", 0, "offline"),
    ("CPE-2214-0001", "BR-EDGE-CHN-01", "VS-2214-00000001", "Chennai DC", "10.20.1.11", 1, "online"),
    ("CPE-2214-0002", "BR-EDGE-HYD-01", "VS-2214-00000002", "Hyderabad DC", "10.20.2.11", 1, "online"),
    ("CPE-2214-0003", "BR-EDGE-KOL-01", "VS-2214-00000003", "Kolkata DC", "10.20.3.11", 1, "unknown"),
]

# Deterministic Keycloak subjects for the demo realm users (see
# keycloak/realm-config/versa-telecom-realm.json `id` fields). Matching the
# assignment subject to the real Keycloak `sub` is what makes the field-engineer
# reveal flow work end to end; keep the two files in sync.
FIELD_DEMO_SUBJECT = "a3333333-3333-3333-3333-333333333333"

# Which demo user subject owns which CPE. The `field` demo user's Keycloak
# subject (above) is pre-assigned so a first-login reveal works without admin action.
DEMO_ASSIGNMENTS = [
    (FIELD_DEMO_SUBJECT, "CPE-2213-0001"),
    (FIELD_DEMO_SUBJECT, "CPE-2214-0001"),
]


def _seed_directors(db: Session, store) -> dict[str, Director]:
    result: dict[str, Director] = {}
    for data in DEMO_DIRECTORS:
        existing = db.scalar(select(Director).where(Director.name == data["name"]))
        if existing:
            result[data["name"]] = existing
            continue
        director = Director(**data)
        db.add(director)
        db.flush()
        result[data["name"]] = director
    db.commit()
    return result


def _seed_cpes(db: Session, directors: dict[str, Director], store) -> None:
    for row in DEMO_CPES:
        cpe_id, name, serial, site, ip, dir_idx, status = row
        existing = db.scalar(select(CPE).where(CPE.cpe_id == cpe_id))
        if existing:
            continue
        director = list(directors.values())[dir_idx]
        cpe = CPE(
            cpe_id=cpe_id,
            device_name=name,
            serial_number=serial,
            site=site,
            management_ip=ip,
            director_id=director.id,
            status=status,
        )
        db.add(cpe)
        db.flush()
        # Create an active credential for each demo CPE.
        ref = f"cred:{cpe_id.lower()}"
        secret = "DemoR0tat!on2026"[:24]
        try:
            store.create_secret(ref, secret)
        except Exception:
            pass
        cred = Credential(
            cpe_id=cpe.id,
            username="admin",
            secret_reference=ref,
            version=1,
            status="ACTIVE",
            rotation_state="ACTIVE",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(cred)
    db.commit()


def _seed_assignments(db: Session) -> None:
    for subject, cpe_id in DEMO_ASSIGNMENTS:
        existing = db.scalar(
            select(CPEAssignment.id).where(
                CPEAssignment.user_subject == subject,
                CPEAssignment.cpe_id == cpe_id,
            )
        )
        if existing is None:
            db.add(CPEAssignment(user_subject=subject, cpe_id=cpe_id))
    db.commit()


def main() -> None:
    settings = get_settings()
    store = build_secret_store(settings)
    db: Session = SessionLocal()
    try:
        directors = _seed_directors(db, store)
        _seed_cpes(db, directors, store)
        _seed_assignments(db)
        logger.info("Demo data seeded")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()