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
  rotation_state: string | null;
  last_accessed_at: string | null;
  last_rotated_at: string | null;
  next_rotation_at: string | null;
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

export interface RotationResult {
  cpe_id: string;
  ok: boolean;
  version?: number;
  error?: string;
}

export interface BulkRotateResponse {
  requested: number;
  results: RotationResult[];
}

export interface PasswordPolicy {
  length: number;
  min_lower: number;
  min_upper: number;
  min_digit: number;
  min_special: number;
}

export interface Director {
  id: number;
  name: string;
  host: string;
  api_base_url: string;
  versa_version: string;
  enabled: boolean;
  capabilities: Record<string, boolean>;
  created_at: string;
}

export interface DirectorStatus {
  reachable: boolean;
  detail: string | null;
  latency_ms: number | null;
}

export interface SyncCpesResult {
  discovered: number;
  created: number;
  updated: number;
}

export interface Assignment {
  user_subject: string;
  username: string | null;
  cpe_id: string;
  device_name: string | null;
  site: string | null;
  assigned_at: string;
}

export interface AdminUser {
  subject: string;
  username: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  roles: string[];
  enabled: boolean;
  last_login_at: string | null;
}

export type AssignmentAction = "assign" | "unassign";

export interface IdentitySyncResult {
  created: number;
  updated: number;
  total: number;
}

export interface KeycloakStatus {
  reachable: boolean;
  realm: string;
  issuer: string;
  console_url: string;
  detail: string | null;
}

export interface LdapStatus {
  admin_api_available: boolean;
  configured: boolean | null;
  provider_names: string[];
  connection_url: string | null;
  edit_mode: string | null;
  enabled: boolean | null;
  detail: string | null;
}

export interface SecretStoreStatus {
  backend: string;
  healthy: boolean;
  detail: string;
}

export interface DirectorCredsStatus {
  directors_count: number;
  api_username_configured: boolean;
  mock_mode: boolean;
  detail: string;
}

export interface BreakGlassStatus {
  local_user_count: number;
  admin_count: number;
  guidance: string;
}

export interface IntegrationStatus {
  keycloak: KeycloakStatus;
  ldap: LdapStatus;
  secret_store: SecretStoreStatus;
  director_creds: DirectorCredsStatus;
  break_glass: BreakGlassStatus;
}