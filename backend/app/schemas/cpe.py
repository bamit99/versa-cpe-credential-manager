from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


class CPEBase(BaseModel):
    cpe_id: str
    device_name: str | None = None
    serial_number: str | None = None
    site: str | None = None
    management_ip: str | None = None


class CPECreate(CPEBase):
    director_id: int | None = None


class CPEUpdate(BaseModel):
    device_name: str | None = None
    serial_number: str | None = None
    site: str | None = None
    management_ip: str | None = None
    status: str | None = None
    director_id: int | None = None
    is_active: bool | None = None


class CPEOut(CPEBase):
    id: int
    status: str
    director_id: int | None = None
    last_seen_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CPESummary(BaseModel):
    id: int
    cpe_id: str
    device_name: str | None = None
    site: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CPEListResponse(BaseModel):
    items: list[CPEOut]
    total: int
    page: int
    page_size: int


class ImportResult(BaseModel):
    created: int
    updated: int


class DirectorCreate(BaseModel):
    name: str
    host: str
    api_base_url: str
    versa_version: str = Field(..., pattern=r"^22\.1\.[34]$")
    oauth_client_id: str
    oauth_secret_ref: str | None = None


class DirectorOut(BaseModel):
    id: int
    name: str
    host: str
    api_base_url: str
    versa_version: str
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignmentRequest(BaseModel):
    user_subject: str
    cpe_id: str