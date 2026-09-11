export interface ApiError {
  detail: string;
  headers?: Record<string, string>;
}

export interface CPE {
  id: number;
  cpe_id: string;
  device_name: string | null;
  serial_number: string | null;
  site: string | null;
  management_ip: string | null;
  director_id: number | null;
  status: string;
  last_seen_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CredentialMeta {
  username: string | null;
  version: number | null;
  status: string | null;
  last_accessed_at: string | null;
  last_rotated_at: string | null;
}

export interface CredentialReveal {
  username: string;
  password: string;
  version: number;
  correlation_id: string;
  display_timeout_seconds: number;
}

export interface AuditEvent {
  id: number;
  timestamp: string;
  user_username: string | null;
  user_role: string | null;
  action: string;
  cpe_id: string | null;
  ticket_reference: string | null;
  source_ip: string | null;
  success: boolean;
  correlation_id: string;
  metadata_json: string | null;
}

export interface AuditLogResponse {
  items: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface CPEListResponse {
  items: CPE[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStats {
  total_cpes: number;
  online_cpes: number;
  offline_cpes: number;
  credentials_needing_rotation: number;
  rotation_failures_recent: number;
  recent_privileged_access: number;
  recent_rotations: number;
}

export interface MeProfile {
  subject: string;
  username: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  roles: string[];
  assigned_cpes: string[];
}