# Versa CPE Credential Manager — MVP

Internal web application to securely manage unique credentials across the Versa
SD-WAN CPE estate (Versa Director 22.1.3 and 22.1.4). Designed so the secret-storage
layer can be swapped to CyberArk / a telecom vault later without architectural changes.

> Reference: `Coding Agent Prompt — Versa Telecom Credential Manager MVP.md`
> Architectural decisions: `DECISIONS.md`

---

## Quick Start (local development)

```bash
# 1. Copy environment template
cp .env.example .env          # then edit the generated values

# 2. Generate the self-signed TLS certificate for nginx
#    (Docker): bash scripts/generate-certs.sh
#    (Windows): powershell -ExecutionPolicy Bypass -File scripts\generate-certs.ps1

# 3. Start the stack (includes mock OpenLDAP via the dev profile)
docker compose --profile dev up --build
```

Once up:

| Service         | URL                          | Credentials (dev)      |
|-----------------|------------------------------|------------------------|
| Web UI          | `https://localhost`          | — sign in via Keycloak |
| Keycloak Admin  | `https://localhost/auth/admin` | admin / `<KC_ADMIN_PASSWORD>` |
| Backend API     | `https://localhost/api/docs` | Bearer token from SSO  |

Self-signed cert ⇒ accept the browser warning once. In production, replace
`nginx/certs/versa-cpe.{crt,key}` with the Corporate PKI certificate (same
filenames, no code change).

### Demo identity (dev realm, disabled in prod configuration)

Realm `versa-telecom` is auto-imported on first Keycloak start:

| Username | Password      | Realm role          |
|----------|---------------|---------------------|
| `admin`  | `Admin12345!` | admin               |
| `ops`    | `Ops12345!`   | security_operator   |
| `field`  | `Field12345!` | field_engineer      |

Demo data (seeded automatically by the backend container):

- 2 Directors — `VD-LABS-2213` (22.1.3) and `VD-LABS-2214` (22.1.4).
- 6 demo CPEs across sites, each with an ACTIVE credential in the mock vault.
  The `field` demo user is pre-assigned to `CPE-2213-0001` and `CPE-2214-0001`.

---

## Architecture

```
Browser ───────── nginx (TLS, rate-limit, headers)
                ├── /            → React SPA (Ant Design)
                ├── /api/        → FastAPI backend
                └── /auth/       → Keycloak
                                     └── LDAP/AD federation (placeholders)
FastAPI ── services ── SecretStore (mock_vault dev / CyberArk later)
        │             CPE / Credential / Rotation / Audit / Versa adapter
        ├── PostgreSQL  (metadata, secret REFERENCES only)
        └── Redis
Versa adapter ── MockVersaClient ──(dev)── VersaDirectorPre23Client (22.1.3+22.1.4, Phase 4)
```

Networks: `frontend-net` (exposed), `backend-net` (internal, no external), `ldap-net` (→ AD).

---

## Security Model

- **Secrets never in PostgreSQL** — only `secret_reference`; values live in the SecretStore.
- No secrets in logs, exceptions, JWT, browser storage, or application config.
- RBAC: `admin` / `security_operator` / `field_engineer`, enforced server-side from
  Keycloak token claims.
- Field engineers must be **assigned** to a CPE to view its credential and must provide
  a reason + ticket.
- Revealed credentials are ephemeral on the client, cleared on timeout, never persisted.
- Append-oriented, immutable-in-practice audit log for all sensitive operations.
- Rate limiting on the auth and API fronts (nginx).

---

## API Overview

Base `/api/v1` (OpenAPI at `/api/docs`):

| Method | Path                    | Access                    | Description |
|--------|-------------------------|---------------------------|-------------|
| GET    | `/cpes`                 | any authenticated         | Inventory (search/filter/sort/paginate) |
| POST   | `/cpes`                 | admin                     | Create CPE |
| PATCH  | `/cpes/{cpe_id}`        | admin                     | Update CPE |
| POST   | `/cpes/import`          | admin                     | CSV import |
| GET    | `/cpes/{cpe_id}`        | any authenticated         | CPE detail |
| GET    | `/cpes/{cpe_id}/credential` | any authenticated     | Credential METADATA (never secret) |
| POST   | `/cpes/{cpe_id}/reveal` | assigned/authorised user  | Authorised secret reveal (audited) |
| POST   | `/cpes/{cpe_id}/rotate` | security_operator/admin   | Single rotation (state machine) |
| POST   | `/rotation/bulk/rotate` | security_operator/admin   | Bulk rotation (bounded) |
| GET    | `/audit`                | security_operator/admin   | Audit log |
| GET    | `/dashboard`            | security_operator/admin   | Stats |
| GET    | `/me`                   | any authenticated         | Profile + assigned CPEs |
| *admin*| `/admin/directors`, `/admin/assignments`, `/admin/password-policy` | admin | |

---

## Rotation safety

Rotation follows a state machine (`ACTIVE → ROTATION_REQUESTED → NEW_SECRET_GENERATED
→ PUSH_TO_CPE → VERIFY_NEW → NEW_SECRET_ACTIVE → OLD_SECRET_RETIRED`). If push or
verification fails, the **old active credential is retained** and the rotation is
marked `ROTATION_FAILED` (new material deleted). Bulk rotations run sequentially with
bounded concurrency on the API.

---

## Tests

```bash
cd backend
pytest -q
```

Coverage targets (per requirements): auth, authorisation, credential randomness,
secret-store interactions, retrieval + authorisation, audit generation, rotation
success/failure/rollback, bulk concurrency, secret redaction, RBAC. A dedicated test
asserts no API response or log accidentally contains a secret apart from the
authorised reveal endpoint.

---

## Production Notes (on-premise / corporate LAN)

1. **Certificate**: replace self-signed certs with Corporate PKI (same filenames).
2. **Keycloak → AD**: `Realm settings → User Federation → Add LDAP provider` using
   `keycloak/realm-config/ldap-federation.json` as a reference once AD details are
   provided. Use LDAPS (636). Edit mode `READ_ONLY` keeps AD authoritative.
3. **Recovery mode**: boot Keycloak with `start --optimized --import-realm` instead of
   `start-dev`.
4. **Database**: secure passwords in `.env`; never commit. Backups are provided via
   `scripts/backup-db.sh` as an integration point for the existing backup solution.
5. **Networking**: only nginx ports (80/443) exposed to the LAN. LDAPS (636) must be
   reachable from the Docker host to the AD domain controllers.
6. **HTTPS-ready headers** (CSP, HSTS, frame/type protection) are applied at nginx.

---

## Roadmap (phased)

- **Phase 1** (done): skeleton, DB + migrations, Keycloak + RBAC, secret-store
  abstraction, mock vault, audit logging, inventory API + UI.
- **Phase 2**: credential generation, retrieval/field-engineer UI, rotation engine — in progress.
- **Phase 3**: real sync service + dashboard extras.
- **Phase 4**: real Versa Director 22.1.3 / 22.1.4 integration — **blocked on lab
  validation** (see `docs/versa-version-matrix.md`). Until then the stack uses the
  mock Versa client and real operations are explicit TODO items.

## Directory Layout

```
backend/         FastAPI app (app/, alembic/, tests/)
frontend/        React + TypeScript + Ant Design SPA
nginx/           Reverse proxy, TLS, security headers
keycloak/        Realm import + AD federation reference
scripts/         Cert generation, DB backup
init-scripts/    PostgreSQL bootstrap (app + Keycloak DBs)
docs/            Architecture & Versa version matrix
DECISIONS.md     Recorded architectural decisions
```