# Production Deployment Guide — Versa CPE Credential Manager

Step-by-step runbook for standing up the manager on a Telecom corporate LAN for
**Production Testing #1** and, where noted, for eventual live operation.

> Read first: `README.md` (architecture/security model) and `DECISIONS.md`
> (§12 readiness review). This guide assumes Ubuntu 22.04/24.04 LTS (or a
> minimal RHEL-9 derivative) with Docker Engine + Compose v2 installed. Windows
> Server with Docker Desktop works too — adjust the path/port hints only.

---

## 0. Scope & reality check

| Layer | Status by end of this runbook |
|---|---|
| Web UI, API, RBAC, audit, rotation (mock) | ✅ fully usable |
| Real Versa Director 22.1.x credential change | ⛔ **Not available** — `NotImplementedError` until lab validation of the API mechanism (see `docs/versa-version-matrix.md`). Rotation operates only via the mock client. |
| Secret storage | ⚠️ `mock_vault` is **DEV-ONLY** (in-memory, no HA/off-box); production-grade store (CyberArk/KMS) is a roadmap item. Use mock vault for Test #1 with the persistence volume in §6; treat as a documented residual risk for anything live. |
| Directory | ⚠️ App works with Keycloak local users now; AD/LDAP federation is ADDITIVE and optional for Test #1. |

If your test objective includes *changing a real CPE password*, stop: that is
Phase 4 and is blocked. Plan Test #1 around API/UI/rotation-engine behaviour
against the mock, and Director connectivity probes only.

---

## 1. Pre-flight checklist

- [ ] Docker + Compose installed on the host; `docker compose version` works.
- [ ] Host can reach:
  - the Keycloak/App/DB no external egress (only LAN).
  - AD/LDAP servers on **LDAPS 636** (when federation is enabled).
  - Versa Directors on **9182/9183** (when Phase 4 lands).
- [ ] DNS name for the UI, e.g. `cpe-mgr.corp.<telecom>.com`, resolves host→same.
- [ ] Corporate PKI cert + key + full chain (`.crt`/`.key`, PEM) for that name.
- [ ] Ports 80/443 free on the host (or pick alternate `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT`).
- [ ] `.env` values agreed (no `change-me…` strings), including a strong
      `KC_ADMIN_CLIENT_SECRET` for the service account.
- [ ] Backup target (NFS/CIFS mount, or existing backup agent) reachable.
- [ ] A Feb 2026 note: Keycloak 26.1 image is pinned; the demo realm JSON is the
      source of truth and is imported on **first** boot only.

---

## 2. Clone / version the code

```bash
git clone <repo> ~/versa-cpe-manager && cd ~/versa-cpe-manager
git fetch --all && git tag -l                      # confirm a test-1 tag exists
git checkout test-1
```

> The working tree must be **committed and tagged** before the team touches it.
> Never run from a dirty/branch-shaped tree in a shared environment.

---

## 3. Secrets: build the production `.env`

Copy `.env.example` to `.env` and replace every value. **Never** commit `.env`
(it is git-ignored). Minimum production-grade values:

| Variable | Guidance |
|---|---|
| `DB_PASSWORD`, `KC_DB_PASSWORD` | ≥ 20 random chars, different per DB |
| `REDIS_PASSWORD` | ≥ 20 random chars |
| `KC_ADMIN_PASSWORD` | strong bootstrap admin password (used once) |
| `KC_ADMIN_CLIENT_SECRET` | ≤ 254-char random secret; must match `versa-cpe-admin` client |
| `KC_DEMO_*_PASSWORD` | placeholder now; **deleted in §9** for production |
| `NGINX_HTTP_PORT` / `NGINX_HTTPS_PORT` | `80` / `443` in production |
| `SECRET_STORE_TYPE` | keep `mock_vault` for Test #1 (see §0/§6) |

Example generator (PowerShell or bash):

```bash
openssl rand -base64 24   # run once per secret field
```

---

## 4. TLS certificates (Corporate PKI)

Replace the dev self-signed certs — same filenames, no code change:

```bash
mkdir -p nginx/certs
cp <client>.crt nginx/certs/versa-cpe.crt
cp <client>.key nginx/certs/versa-cpe.key
chmod 600 nginx/certs/versa-cpe.key
```

Make sure the cert covers the DNS name in §1. `openssl x509 -in nginx/certs/versa-cpe.crt -noout -subject -ext subjectAltName`.

Until PKI is swapped in, you can generate self-signed for bring-up:
`scripts/generate-certs.sh` (Linux) / `scripts/generate-certs.ps1` (Windows).

---

## 5. Production Compose override

Create `docker-compose.prod.yml` **next** to the existing file. It overrides the
dev defaults (production ports, real hostname, Keycloak **production mode**,
persistent mock-vault, and a DB backup mount). Keep the base `docker-compose.yml`
untouched so `--profile dev` still works for development.

```yaml
# docker-compose.prod.yml — production overrides for Test #1
services:
  nginx:
    ports:
      - "${NGINX_HTTP_PORT:-80}:80"
      - "${NGINX_HTTPS_PORT:-443}:443"

  frontend:
    build:
      args:
        - VITE_API_URL=https://cpe-mgr.corp.example.com/api/v1
        - VITE_KEYCLOAK_URL=https://cpe-mgr.corp.example.com/auth
        # realm/client id unchanged

  backend:
    environment:
      - KEYCLOAK_PUBLIC_URL=https://cpe-mgr.corp.example.com/auth   # token issuer host
      - MOCK_VAULT_FILE=/data/mock_vault.enc                        # persist demo vault
      - MOCK_VAULT_PASSPHRASE=${MOCK_VAULT_PASSPHRASE}              # strong, dev-only store
    volumes:
      - mock_vault_data:/data

  keycloak:
    entrypoint:
      - /bin/sh
      - -c
      - "/opt/keycloak/bin/kc.sh import --dir=/opt/keycloak/data/import --override=false; exec /opt/keycloak/bin/kc.sh start"
    environment:
      - KC_HOSTNAME=https://cpe-mgr.corp.example.com/auth
      - KC_HOSTNAME_STRICT=true
      # KC_PROXY_HEADERS=xforwarded and KC_HTTP_RELATIVE_PATH=/auth inherited from base

  postgres:
    volumes:
      - ./scripts/backup-db.sh:/usr/local/bin/backup-db.sh:ro
      - /backups:/backups:rw

volumes:
  mock_vault_data:
```

> **Keycloak mode.** The base file uses `start-dev`; production must use
> `kc.sh start` (non-dev). `--optimized` is only valid on an image that was
> pre-baked with `kc.sh build` — do NOT add it to a vanilla image.
>
> **Backup script.** `scripts/backup-db.sh` defaults to dumping DB `postgres`
> (not `versa_cpe`). For Test #1 back up the app DB explicitly:
> `docker compose exec postgres pg_dump -U "$DB_USER" "$DB_NAME" | gzip > /backups/versa_cpe_$(date +%F).sql.gz`.

---

## 6. Persist the mock vault (Test #1 only)

The mock secret store holds the actual credential values. Without a volume they
vanish when the backend container is recreated and every CPE hits
"Secret store miss". The override above mounts `mock_vault_data` at `/data` and
points `MOCK_VAULT_FILE` at it.

- Add `MOCK_VAULT_PASSPHRASE=…` (random) to `.env`.
- Log this clearly in the test report as a known limitation: **mock vault is
  single-node, not HA, not audited at the store, and is not a production vault.**

---

## 7. Bring the stack up

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config   # sanity-check merge
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps       # all healthy
```

Wait for Keycloak first-boot import (realm `versa-telecom` created):

```bash
docker compose logs -f keycloak
```

When the realm import finishes you will see the realm in the log. The backend
entrypoint waits for Postgres, runs `alembic upgrade head`, then seeds demo data.

---

## 8. Post-boot verification (Test #1 gate)

Run these and record the output in the test report:

```bash
# 1. TLS endpoint responds
curl -sk https://cpe-mgr.corp.example.com/health -o /dev/null -w "%{http_code}\n"   # 200

# 2. OIDC discovery reachable through nginx
curl -sk https://cpe-mgr.corp.example.com/auth/realms/versa-telecom/.well-known/openid-configuration | head -c 200

# 3. Login flow visually (browser) as a field engineer
#    - realm: versa-telecom  client: versa-cpe-manager
#    - reveal a credential for CPE-2213-0001 → the assignment now matches the
#      deterministic subject (DECISIONS §12.2.4 fix)

# 4. Demo role walk-through (browser): admin / security_operator / field_engineer
# 5. Single + bulk rotation through the UI (mock Director) → audit rows appear
# 6. Integrations page shows Keycloak reachable, LDAP "not configured" (expected), break-glass admin count ≥ 1
# 7. Sync from Keycloak pulls the three demo users into Admin → Users
```

Any `5xx`, "Secret store miss", or 403 on the field reveal = stop and log before
proceeding.

> Full click-by-click test matrix with pass/fail fields and a sign-off sheet:
> `docs/test-1-lab-runbook.md`.

---

## 9. Production hardening (before opening access to the team)

1. **Remove demo identities.** `Keycloak Admin → users` → delete `admin`, `ops`,
   `field`; keep or create one local break-glass admin. Clear/replace the demo
   passwords first if staying in place for play-testing.
2. **Edit the SPA client** `versa-cpe-manager`:
   - `Valid redirect URIs` → `https://cpe-mgr.corp.example.com/*`
   - `Web origins` → `https://cpe-mgr.corp.example.com`
   - remove `http://localhost:3000/*`.
3. **Lock the admin client** `versa-cpe-admin`: confirm service account and that
   `KC_ADMIN_CLIENT_SECRET` is strong and rotated from the import default.
4. **Realm import once.** With a populated DB the import runs with
   `--override=false` (idempotent). Do not re-run `kc.sh import` ad hoc.
5. **Wipe demo seed data** from Postgres (re-seed is env-idempotent and guarded):
   delete rows from `cpes`, `credentials`, `cpe_assignments`, `directors` that
   match the demo pattern, **or** re-create the DB and import without the demo
   users. The cleanest path for a real rollout: a fresh DB + a realm import that
   contains only real/AAD-provisioned users.

### 9.1 AD/LDAP federation (optional but recommended)

1. `Keycloak Admin → Realm settings → User federation → Add LDAP provider`.
2. Use `keycloak/realm-config/ldap-federation.json.example` as the reference
   skeleton. Replace:
   - `connectionUrl=ldaps://dc.corp.example.com:636`
   - `bindDn` / `bindCredential` (read-only service account, least privilege)
   - `usersDn`, `usernameLdapAttribute`, `rdnLdapAttribute`,
     `userObjectClasses`, group mapping
3. Import mode `READ_ONLY`, **edit mode `READ_ONLY`** (AD stays authoritative),
   `LDAPS only` (636). Enable `import` users so Keycloak mirrors them into ITS
   local store — the app's "Sync from Keycloak" then pulls the same set.
4. Map AD **groups** → realm roles `admin` / `security_operator` / `field_engineer`.
5. Never store LDAP passwords in this repo; they live in Keycloak config only.
6. Confirm the app's Integrations page flips: `ldap.configured → true`.

> The Docker host needs LDAPS route to the domain controllers. The compose
> `ldap-net` network is the integration point.

### 9.2 Secrets & keys

- Rotate `KC_ADMIN_CLIENT_SECRET` and DB/Redis passwords before the team is
  invited.
- The service-account secret is injected at realm import from env — rotation
  requires updating client secret in Keycloak AND `.env` together.

---

## 10. Backup / restore / DR

Daily (cron or the existing backup agent):

```bash
# app DB
docker compose exec postgres pg_dump -U "$DB_USER" "$DB_NAME" | gzip > /backups/versa_cpe_$(date +%F).sql.gz
# Keycloak DB
docker compose exec postgres pg_dump -U "$KC_DB_USER" keycloak | gzip > /backups/keycloak_$(date +%F).sql.gz
# mock vault (Test #1 only) — value store!
docker compose exec backend cp /data/mock_vault.enc /backups/mock_vault_$(date +%F).enc
# prune > 7 days
find /backups -name '*.gz' -mtime +7 -delete
```

Restore drill (quarterly):

```bash
docker compose down
# restore .gz dumps via pg_restore/psql against a fresh postgres volume
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

> Keycloak config (realm + clients + federation) is code (realm JSON) and images;
> the Keycloak DB holds runtime state. Restoring both DBs + the vault file gives
> a recoverable point-in-time.

---

## 11. Day-2 operations

- **Monitoring**: probe `/health` (nginx → backend) every 30 s; alert on non-200.
  Enable Keycloak metrics (`KC_METRICS_ENABLED=true` already set) and scrape
  `:8080/metrics` inside the backend network if desired.
- **Logs**: `docker compose logs --tail 200 backend nginx keycloak`; ship to the
  SIEM. Secrets are redacted by design — a log-based regression test enforces it.
- **Audit trail**: the in-app audit log is append-only; export `/api/v1/audit`
  periodically for the SIEM if the SIEM integration is not yet built.
- **Upgrades**: commit/image-tag every tested snapshot (e.g. `test-1`). Upgrade =
  pull tag → `docker compose up -d --build` → run verification block §8.
- **Capacity** (§13 requirements): Postgres must hold ≥ 5,000 CPE rows; give the
  host 4 vCPU / 8 GB RAM minimum and a 40 GB volume for `postgres_data` +
  `redis_data`.

---

## 12. Explicit out-of-scope / residual risks for Test #1

| Item | Risk | Status |
|---|---|---|
| Real Director rotation | Cannot work until lab validates `change-password`/`setLocalUserPassword` | Blocked (Phase 4) |
| Mock vault | No HA, single-node, in-memory; password material at risk if host is compromised | Dev-only; use §6 volume for tests |
| Self-signed → HSTS | If you keep the self-signed cert and HSTS is on, a cert change locks clients out for 1 year (`max-age=31536000`). Disable HSTS until PKI is in place, or accept the browser exception before testing. | Configure in nginx for prod |
| Demo identities in realm | Demo users/passwords exist until §9 is run | Do §9 before team access |
| Video-grade CPE scale (3000+) | Untested at scale; load-test `/cpes` and bulk rotation ≤ 100/batch before claiming production capacity | Test #1 input |
| CI pipeline | No CI is committed; every deploy is manual | Recommended squad action |
| Frontend automated tests | None (tsc only) | Tracked gap §12.2.6 |

---

## 13. Recommended next milestones

1. **Test #1 (this runbook)** — mock-mode team UAT on the LAN: UI flow, RBAC,
   audit, rotation engine, Integrations page, identity sync, backup/restore drill.
2. **Security review** — threat model (`Deliverables` §8 of the requirements doc),
   AD federation trial with a sub-OU, certificate swap to PKI, HSTS finalisation.
3. **Phase 4** — lab validation of Director credential-change on 22.1.3 + 22.1.4,
   then wire the real client + per-Director credential model.
4. **Production** — real secret store (CyberArk/KMS), CI/CD, SIEM export, load
   test at 3,000+ CPEs, HA (multi-node backend + managed Postgres).