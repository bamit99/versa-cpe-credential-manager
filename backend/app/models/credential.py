from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CredentialStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    ROTATION_REQUESTED = "ROTATION_REQUESTED"
    NEW_SECRET_GENERATED = "NEW_SECRET_GENERATED"
    PUSH_TO_CPE = "PUSH_TO_CPE"
    VERIFY_NEW = "VERIFY_NEW"
    ROTATION_FAILED = "ROTATION_FAILED"
    NEW_ACTIVE = "NEW_ACTIVE"
    RETIRED = "RETIRED"


class RotationState(str, Enum):
    ACTIVE = "ACTIVE"
    ROTATION_REQUESTED = "ROTATION_REQUESTED"
    NEW_SECRET_GENERATED = "NEW_SECRET_GENERATED"
    PUSH_TO_CPE = "PUSH_TO_CPE"
    VERIFY_NEW = "VERIFY_NEW"
    ROTATION_FAILED = "ROTATION_FAILED"
    NEW_SECRET_ACTIVE = "NEW_SECRET_ACTIVE"
    OLD_SECRET_RETIRED = "OLD_SECRET_RETIRED"


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpe_id: Mapped[int] = mapped_column(ForeignKey("cpes.id"), index=True)
    username: Mapped[str] = mapped_column(String(255))
    # The actual secret lives in the SecretStore; ONLY a reference is stored here.
    secret_reference: Mapped[str] = mapped_column(String(255), unique=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32), default=CredentialStatus.ACTIVE.value)
    rotation_state: Mapped[str] = mapped_column(String(32), default=RotationState.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_rotation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cpe: Mapped[CPE] = relationship(back_populates="credentials")


from app.models.cpe import CPE  # noqa: E402