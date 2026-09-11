"""SQLAlchemy model registry (imports guarantee Alembic autodetect sees all tables)."""
from app.models.cpe import CPE, Director, User
from app.models.credential import Credential, RotationState, CredentialStatus
from app.models.access import AccessRequest, CPEAssignment
from app.models.audit import AuditEvent

__all__ = [
    "CPE",
    "Director",
    "User",
    "Credential",
    "RotationState",
    "CredentialStatus",
    "AccessRequest",
    "CPEAssignment",
    "AuditEvent",
]