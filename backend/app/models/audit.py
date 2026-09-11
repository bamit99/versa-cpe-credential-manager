from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditEvent(Base):
    """Append-oriented audit trail. NOT updateable/deletable by normal users."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_user_action", "user_subject", "action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    user_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    user_username: Mapped[str | None] = mapped_column(String(255))
    user_role: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), index=True)
    cpe_id: Mapped[str | None] = mapped_column(String(128), index=True)
    ticket_reference: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(String(1024))
    source_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    success: Mapped[bool] = mapped_column(default=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[str | None] = mapped_column(String(4096))  # non-secret details

    @property
    def is_audit_immutable(self) -> bool:
        return True