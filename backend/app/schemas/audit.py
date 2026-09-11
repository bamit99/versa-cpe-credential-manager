from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: int
    timestamp: datetime
    user_username: str | None = None
    user_role: str | None = None
    action: str
    cpe_id: str | None = None
    ticket_reference: str | None = None
    reason: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    success: bool
    correlation_id: str
    metadata_json: str | None = None

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int


class DashboardStats(BaseModel):
    total_cpes: int
    online_cpes: int
    offline_cpes: int
    credentials_needing_rotation: int
    rotation_failures_recent: int
    recent_privileged_access: int
    recent_rotations: int