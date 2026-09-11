from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AccessRequest(Base):
    """A field-engineer credential retrieval request (reason + ticket)."""

    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    cpe_id: Mapped[int] = mapped_column(ForeignKey("cpes.id"), index=True)
    reason: Mapped[str] = mapped_column(String(1024))
    ticket_reference: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="granted")  # granted/denied
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    cpe: Mapped[CPE] = relationship()


class CPEAssignment(Base):
    """MVP authorisation model: Keycloak subject -> CPE assignment."""

    __tablename__ = "cpe_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_subject: Mapped[str] = mapped_column(String(255), index=True)
    cpe_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cpe: Mapped[CPE] = relationship(
        primaryjoin="CPEAssignment.cpe_id==CPE.cpe_id",
        foreign_keys="[CPEAssignment.cpe_id]",
        back_populates="assignments",
    )


from app.models.cpe import CPE, User  # noqa: E402