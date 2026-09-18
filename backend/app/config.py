from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Versa CPE Credential Manager"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql://versa_app:change-me-db-password@localhost:5432/versa_cpe"
    redis_url: str = "redis://:change-me-redis-password@localhost:6379/0"

    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "versa-telecom"
    keycloak_client_id: str = "versa-cpe-manager"
    keycloak_client_secret: str = ""

    # Public issuer used in token validation. When Keycloak sits behind a proxy
    # (KC_HTTP_RELATIVE_PATH=/auth + proxy headers), tokens carry the public
    # frontend URL as issuer while the backend reaches Keycloak via the internal
    # URL. Empty falls back to keycloak_url.
    keycloak_public_url: str = ""

    # Optional dedicated admin-API endpoint/service account (identity sync).
    # Empty admin_url falls back to keycloak_url; the admin client must hold
    # realm-management roles to read users and role mappings.
    keycloak_admin_url: str = ""
    keycloak_admin_client_id: str = "admin-cli"
    keycloak_admin_client_secret: str = ""

    # Versa Director API console account for the pre-23 REST client (OAuth password
    # grant). Real deployments resolve these strictly outside the DB; the secret
    # store reference on the Director row (oauth_secret_ref) carries the client
    # secret. Lab verification determines the final per-director credential model.
    versa_api_username: str = ""
    versa_api_password: str = ""

    secret_store_type: str = "mock_vault"

    credential_display_timeout_seconds: int = 180
    credential_default_length: int = 24
    rotation_due_days: int = 90
    rotation_interval_days: int = 90

    # CORS — restricted to the TLS origin of the stack.
    cors_origins: list[str] = ["https://localhost", "http://localhost:3000"]

    @property
    def issuer(self) -> str:
        base = self.keycloak_public_url or self.keycloak_url
        return f"{base}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()