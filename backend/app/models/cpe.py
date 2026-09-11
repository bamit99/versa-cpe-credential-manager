from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    """Mirror of the authenticated identity (Keycloak). No passwords stored."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    roles: Mapped[list[str]] = mapped_column(  # persisted from Keycloak claims
        "roles_json",
        String(2048),
        default="[]",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Director(Base):
    """Versa Director node. One entry per VD endpoint."""

    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    host: Mapped[str] = mapped_column(String(255))
    api_base_url: Mapped[str] = mapped_column(String(255))  # e.g. https://director.example.com:9183
    versa_version: Mapped[str] = mapped_column(String(32))  # e.g. 22.1.3 / 22.1.4
    oauth_client_id: Mapped[str] = mapped_column(String(255))
    # Secret to the Director lives in the SecretStore; only a reference here.
    oauth_secret_ref: Mapped[str | None] = mapped_column(String(255))
    # Per-operation capability flags (which API ops are verified on this version).
    capabilities_json: Mapped[str] = mapped_column(String(2048), default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cpes: Mapped[list[CPE]] = relationship(back_populates="director")


class CPE(Base):
    __tablename__ = "cpes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpe_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    device_name: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255), index=True)
    site: Mapped[str | None] = mapped_column(String(255), index=True)
    management_ip: Mapped[str | None] = mapped_column(String(64))
    director_id: Mapped[int | None] = mapped_column(ForeignKey("directors.id"))
    status: Mapped[str] = mapped_column(String(32), default="unknown")  # online/offline/unknown
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    director: Mapped[Director | None] = relationship(back_populates="cpes")
    credentials: Mapped[list[Credential]] = relationship(
        back_populates="cpe", cascade="all, delete-orphan"
    )
    assignments: Mapped[list[CPEAssignment]] = relationship(
        back_populates="cpe",
        primaryjoin="CPE.cpe_id==CPEAssignment.cpe_id",
        foreign_keys="[CPEAssignment.cpe_id]",
        cascade="all, delete-orphan",
    )


from app.models.access import CPEAssignment  # noqa: E402
from app.models.credential import Credential  # noqa: E402