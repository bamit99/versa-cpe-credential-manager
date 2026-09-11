"""Application entrypoint."""
from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin, audit, cpe, credential, dashboard, me, rotation
from app.config import get_settings
from app.db.session import Base, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# Never log credential material.
logging.getLogger("app.services.secret_store").setLevel(logging.WARNING)
logging.getLogger("app.adapters").setLevel(logging.WARNING)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-fetch JWKS so the first request doesn't pay the round-trip. Non-fatal.
    try:
        from app.auth.keycloak import get_keycloak_auth

        get_keycloak_auth(settings)._jwks_client.get_jwk_set()
        logging.getLogger("app").info("Keycloak JWKS keys cached at startup")
    except Exception as exc:  # pragma: no cover - resilience only
        logging.getLogger("app").warning("Could not pre-cache JWKS keys: %s", exc)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cpe.router, prefix="/api/v1/cpes", tags=["CPE"])
app.include_router(credential.router, prefix="/api/v1", tags=["Credentials"])
app.include_router(rotation.router, prefix="/api/v1", tags=["Rotation"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(me.router, prefix="/api/v1", tags=["Me"])


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}