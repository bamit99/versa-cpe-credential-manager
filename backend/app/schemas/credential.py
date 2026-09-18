from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.credential import CredentialStatus


class CredentialOut(BaseModel):
    id: int
    cpe_id: int
    username: str
    version: int
    status: str
    rotation_state: str
    created_at: datetime
    activated_at: datetime | None = None
    retired_at: datetime | None = None
    last_accessed_at: datetime | None = None
    last_rotated_at: datetime | None = None
    next_rotation_at: datetime | None = None

    model_config = {"from_attributes": True}


class CredentialRevealResponse(BaseModel):
    username: str
    password: str = Field(..., description="Revealed credential value (ephemeral display only)")
    version: int
    correlation_id: str
    display_timeout_seconds: int = 180


class AccessRequestCreate(BaseModel):
    reason: str = Field(..., min_length=4, max_length=1024)
    ticket_reference: str | None = Field(default=None, max_length=255)


class AccessRequestOut(BaseModel):
    id: int
    user_id: int
    cpe_id: int
    reason: str
    ticket_reference: str | None = None
    status: str
    correlation_id: str
    requested_at: datetime
    granted_at: datetime | None = None

    model_config = {"from_attributes": True}


class RotationRequest(BaseModel):
    """Empty body — rotation always applies to the current active credential."""
    pass


class PasswordPolicyOut(BaseModel):
    length: int
    min_lower: int
    min_upper: int
    min_digit: int
    min_special: int


class PasswordPolicyUpdate(BaseModel):
    length: int = Field(default=24, ge=12, le=128)
    min_lower: int = Field(default=1, ge=0, le=128)
    min_upper: int = Field(default=1, ge=0, le=128)
    min_digit: int = Field(default=1, ge=0, le=128)
    min_special: int = Field(default=1, ge=0, le=128)