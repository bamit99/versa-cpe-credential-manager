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

    secret_store_type: str = "mock_vault"

    credential_display_timeout_seconds: int = 180
    credential_default_length: int = 24

    # CORS — restricted to the TLS origin of the stack.
    cors_origins: list[str] = ["https://localhost", "http://localhost:3000"]

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()