"""Keycloak OIDC integration.

Validates access tokens locally against Keycloak's JWKS endpoint (no round-trip
per request). Roles are read from the token claims and drive RBAC. No secret is
read from the token beyond what Keycloak signs into it.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


class TokenUser(BaseModel):
    subject: str
    username: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    roles: list[str] = Field(default_factory=list)

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _extract_claims(payload: dict, settings: Settings) -> TokenUser:
    realm_roles = payload.get("realm_access", {}).get("roles", [])
    client_roles = (
        payload.get("resource_access", {})
        .get(settings.keycloak_client_id, {})
        .get("roles", [])
    )
    return TokenUser(
        subject=payload.get("sub", ""),
        username=payload.get("preferred_username", ""),
        email=payload.get("email"),
        first_name=payload.get("given_name"),
        last_name=payload.get("family_name"),
        roles=list(dict.fromkeys([*realm_roles, *client_roles])),
    )


class KeycloakAuth:
    """Caches JWKS keys and validates tokens on demand."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jwks_client = PyJWKClient(
            settings.jwks_url,
            cache_keys=True,
            lifespan=3600,
        )

    def validate_token(self, token: str) -> TokenUser:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt_decode_verified(
                token,
                signing_key.key,
                issuer=self._settings.issuer,
            )
        except InvalidTokenError as exc:
            logger.info("Token validation failed: %s", str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Keycloak JWKS endpoint",
            ) from exc
        return _extract_claims(payload, self._settings)


def jwt_decode_verified(token: str, key, issuer: str) -> dict:
    # imported lazily to keep module import light and make the dependency clear
    from jwt import decode

    return decode(
        token,
        key,
        algorithms=["RS256"],
        audience="account",
        issuer=issuer,
        options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
    )


_auth: KeycloakAuth | None = None


def get_keycloak_auth(settings: Settings = Depends(get_settings)) -> KeycloakAuth:
    global _auth
    if _auth is None:
        _auth = KeycloakAuth(settings)
    return _auth


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth: KeycloakAuth = Depends(get_keycloak_auth),
) -> TokenUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth.validate_token(credentials.credentials)


def _require_roles(*roles: str):
    """Dependency factory: ensures the caller holds at least one of the given roles."""

    def _dependency(user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if not any(r in user.roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required role: one of {', '.join(roles)}",
            )
        return user

    return _dependency


# Role-gated dependencies used across the API.
require_admin = _require_roles("admin")
require_security_operator = _require_roles("admin", "security_operator")
require_any_authenticated = _require_roles("admin", "security_operator", "field_engineer")


def parse_roles_json(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except ValueError:
        return []


def now_utc() -> datetime:
    return datetime.now(timezone.utc)