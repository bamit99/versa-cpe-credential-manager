from __future__ import annotations

from pydantic import BaseModel


class KeycloakStatus(BaseModel):
    reachable: bool
    realm: str
    issuer: str
    console_url: str
    detail: str | None = None


class LdapStatus(BaseModel):
    """LDAP/AD user federation as seen through Keycloak's Admin REST API.

    Read-only: the app reports whether a provider exists and its key settings,
    but never creates or mutates it (that stays in the Keycloak Admin Console).
    """

    admin_api_available: bool
    configured: bool | None = None
    provider_names: list[str] = []
    connection_url: str | None = None
    edit_mode: str | None = None
    enabled: bool | None = None
    detail: str | None = None


class SecretStoreStatus(BaseModel):
    backend: str
    healthy: bool
    detail: str


class DirectorCredsStatus(BaseModel):
    directors_count: int
    api_username_configured: bool
    mock_mode: bool
    detail: str


class BreakGlassStatus(BaseModel):
    local_user_count: int
    admin_count: int
    guidance: str


class IntegrationStatusOut(BaseModel):
    keycloak: KeycloakStatus
    ldap: LdapStatus
    secret_store: SecretStoreStatus
    director_creds: DirectorCredsStatus
    break_glass: BreakGlassStatus
