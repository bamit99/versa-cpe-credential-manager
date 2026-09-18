# Production Test #1 — Lab Runbook (for Ops)

Written for **operations engineers, not developers**. You do **not** need to read
code, run builds, or run the test suite. Everything below is click-by-click with a
pass/fail column. Print this, open the app in a browser, and work top to bottom.

> Companion docs: `docs/production-deployment.md` (how the stack was built and
> configured) and `README.md` (architecture). This runbook assumes the lab stack
> is **already running** in mock mode.

---

## 0. The 30-second summary

- What we test: **everyday operator + admin workflows** — login, inventory,
  credential reveal & audit, single/bulk rotation, dashboard, admin pages.
- What we do **NOT** test (out of scope for Test #1):
  - Changing a **real** CPE password on a Versa Director. The real client is
    staged but not enabled until lab validation, so rotation runs against a
    **mock**. Record this in the report.
  - AD/LDAP federation (not configured yet — checks on the Integrations page
    will show "not configured", which is **expected**).
- Time: roughly **1.5–2 hours** for two people.
- If anything shows a red result, fill the Defect Log (§7) and continue.

---

## 1. Lab prerequisites (confirm before staring the run)

| # | Check | Who | Done? |
|---|-------|-----|-------|
| 1 | Lab box has Docker + Compose; `docker compose version` prints a version | Lab owner | ☐ |
| 2 | Code checked out at a fixed tag (`git describe` shows `test-1`) | Lab owner | ☐ |
| 3 | `.env` exists with real (non-`change-me`) passwords and demo passwords recorded on the lab secrets sheet | Lab owner | ☐ |
| 4 | TLS certs in `nginx/certs/` (self-signed OK for lab) | Lab owner | ☐ |
| 5 | Stack is up: `docker compose ps` shows 6 containers, none "Exit" | Lab owner | ☐ |
| 6 | Browser tab open at `https://<lab-host>/` (accept the self-signed warning once) | All | ☐ |
| 7 | Demo passwords handy for `admin`, `ops`, `field` (from the lab secrets sheet) | All | ☐ |

**Stack commands the lab owner may need** (Ops-safe copy-paste):

```bash
# start (first time also builds)
docker compose --profile dev up --build -d

# stop (keeps data)
docker compose stop

# restart after config change
docker compose restart backend nginx

# FULL reset (wipes DB + Keycloak realm + mock vault — demo data returns)
docker compose down -v && docker compose --profile dev up --build -d

# live logs
docker compose logs -f backend
```

> ⚠️ **Mock vault reminder.** If the backend container is recreated, credential
> values vanish unless a vault volume was configured (see production guide §6).
> On a full reset (`down -v`) that is fine — demo data is re-seeded.

---

## 2. Who signs in as what

| Login | Role | What they should be able to do |
|-------|------|--------------------------------|
| `admin` | admin | everything |
| `ops` | security_operator | inventory, reveal (no restriction), rotations, audit, dashboard |
| `field` | field_engineer | only ASSIGNED CPEs; reveal requires a reason/ticket; **no** admin or rotation pages |

Open the app, click **Sign in**, and use the realm `versa-telecom`
(presented automatically).

---

## 3. Test matrix (work top to bottom)

Each row: the role that performs it → steps → expected result → your verdict.

### 3.1 Login & health

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-01 | Lab owner | Terminal: `curl -sk https://<lab-host>/health` | Returns `{"status":"healthy"}` and HTTP 200 | ☐ |
| TC-02 | all | Sign in as `admin`, then `ops`, then `field` in turn (log out between) | Each lands on the Dashboard after the Keycloak sign-in screen | ☐ |
| TC-03 | all | Refresh the page mid-session | Still signed in (token refresh works), no "Unable to contact identity provider" | ☐ |

### 3.2 Inventory & detail (field_engineer + operator)

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-04 | ops | Inventory page: search for `CPE-2213`, filter status, paginate to page 2 and back | Results load; search/filter/sort/pagination all work | ☐ |
| TC-05 | ops | Open a CPE detail page | Shows device info + **credential metadata only** (username, status, next rotation) — **never the password** | ☐ |
| TC-06 | field | Inventory shows only CPEs they can access (CPE-2213-0001, CPE-2214-0001) | List is limited to assigned CPEs | ☐ |

### 3.3 Credential reveal (the critical access-control test)

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-07 | field | On **assigned** CPE → **Reveal credential** → fill Reason + Ticket → confirm | Password is shown briefly, then **clears itself** (timeout). It is NEVER shown again on refresh | ☐ |
| TC-08 | field | Refresh the page after reveal | Credential is NOT displayed again (ephemeral) | ☐ |
| TC-09 | field | Try to reveal a **non-assigned** CPE (e.g. search in admin-assigned list only) | Blocked — access denied message; no secret shown | ☐ |
| TC-10 | field | Reveal **without** entering a reason or ticket | Request rejected ("reason/ticket required") | ☐ |
| TC-11 | ops | Reveal a credential (no reason needed for ops/admin) | Works; shown then cleared | ☐ |

### 3.4 Rotation (operator)

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-12 | ops | CPE Detail → **Rotate** on an ACTIVE credential | Rotation succeeds; new version shown; "next rotation" date jumps forward; success shown | ☐ |
| TC-13 | ops | **Rotation** page → select several due CPEs → **Rotate selected** | Per-CPE success/failure summary; no error for the batch | ☐ |
| TC-14 | ops | Open the same CPE again after rotating | Credential metadata shows incremented version and new next-rotation date | ☐ |
| TC-15 | ops | Rotate a CPE that is mid-rotation | Click again immediately after a rotate — app refuses with "rotation already in progress" (state machine guard) | ☐ |

> Note: the **failed-rotation** path (push/verify failure → old credential kept)
> cannot be triggered from the UI in mock mode because the mock always succeeds.
> It is covered by the automated unit suite. Record as "covered by CI, not
> UI-testable in lab" in the report.

### 3.5 Audit & dashboard

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-16 | ops | **Audit** page → filter by Action | Shows the actions performed today (reveals, rotations, logins) with user, time, CPE, success/fail | ☐ |
| TC-17 | ops | Pick a reveal you just made and check the audit row | Row exists, has correlation ID, **no password** anywhere | ☐ |
| TC-18 | ops + admin | **Dashboard** after the above steps | Counts moved: recent rotations, recent privileged access, credentials needing rotation reflect your actions | ☐ |

### 3.6 Role enforcement (do a "bad operator" pass)

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-19 | field | Try to open Admin, Rotation, or Audit pages directly | Access denied / page hidden; backend also returns 403 (confirmed by network tab) | ☐ |
| TC-20 | ops | Try the **Settings / Users** admin pages | Hidden / denied (admin-only) | ☐ |
| TC-21 | ops | Try **Rotate** on a CPE you can see | Works (security_operator is allowed) | ☐ |

### 3.7 Admin surfaces (admin account)

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-22 | admin | **Admin → Users** → **Sync from Keycloak** | Shows 3 users (admin, ops, field) with roles; enabled tick | ☐ |
| TC-23 | admin | **Admin → Assignments** → pick `field` engineer → assign them to a CPE → remove and re-add | Assignment saves; then sign in as `field` and confirm that CPE is now revealable / no longer revealable | ☐ |
| TC-24 | admin | **Admin → Directors** → Probe a Director | Reachability tag appears (unreachable is OK for `.example.com` hosts — log the result) | ☐ |
| TC-25 | admin | **Admin → Directors** → **Pull CPEs** | CPE count increases / automatically discovered (mock returns 5 per Director) | ☐ |
| TC-26 | admin | **Admin → Integrations** | Cards show: Keycloak reachable, **LDAP not configured (expected)**, secret store = mock/dev, directors count ≥ 1, break-glass admin ≥ 1 | ☐ |
| TC-27 | admin | **Admin → Settings** → lengthen password minimums → save | Saved without error; next rotation generates a password meeting the new policy (rotate one CPE to confirm) | ☐ |
| TC-28 | admin | **Admin → Settings** → set an impossible policy (e.g. require 30 chars total but 20 lower + 20 upper) | Rejected with a validation message; nothing saved | ☐ |

### 3.8 Security spot-checks

| ID | Role | Steps | Expected | Pass/Fail |
|----|------|-------|----------|-----------|
| TC-29 | lab owner | From terminal call the CPE detail API without a token: `curl -sk https://<lab-host>/api/v1/cpes` | 401 Not authenticated | ☐ |
| TC-30 | lab owner | Call `/api/v1/audit` as a **field** token (or reuse a field session token) | 403 Forbidden | ☐ |
| TC-31 | lab owner | Search the browser console/network for any reveal response containing the demo password pattern | Nothing but the reveal endpoint returns it | ☐ |
| TC-32 | all | Confirm logout works and going back (browser back) doesn't re-expose the session | Restart from sign-in screen | ☐ |

---

## 4. Clean shutdown & what to record

1. Note the app version shown in the UI/API (`GET /api/v1` docs title) and the git tag.
2. Note the exact lab date + host name.
3. Ask each engineer for a line about anything that felt awkward or was missing
   (UX, wording, missing field). These are inputs for Test #2, not failures.

If the lab stays up for repeat testing, keep the stack running
(`docker compose stop` at night, `start` in the morning; data persists). For a
completely clean slate use the FULL reset command in §1.

---

## 5. Sign-off summary (paste into your report)

| Section | Green count | Red count |
|---------|-------------|-----------|
| 3.1 Login & health | ☐ | ☐ |
| 3.2 Inventory & detail | ☐ | ☐ |
| 3.3 Credential reveal | ☐ | ☐ |
| 3.4 Rotation | ☐ | ☐ |
| 3.5 Audit & dashboard | ☐ | ☐ |
| 3.6 Role enforcement | ☐ | ☐ |
| 3.7 Admin surfaces | ☐ | ☐ |
| 3.8 Security spot-checks | ☐ | ☐ |

**Overall recommendation for Production Testing #2:**  Proceed ☐ / Fix first ☐

Signed: ____________________  Date: __________

---

## 6. Known limitations to state in the report

1. **Real Director rotation is NOT exercised** — mock only, until the Phase 4 lab
   confirms the 22.1.x credential-change mechanism.
2. **Secret store is the dev mock vault** — single-node, in-memory (volume
   persisted in the lab), no HA/audit-at-store. A real vault (CyberArk/KMS) is a
   later phase.
3. **AD/LDAP not wired** — realm local users were used; Integrations page shows
   LDAP "not configured" as expected.
4. **Failed-rotation UI path** (rollback of new material, old retained) is
   covered by automated tests, not UI-testable in mock mode.
5. **Scale (3,000+ CPEs) not tested** — bulk rotation is capped at 100/batch by
   design; load-testing is a separate milestone.

---

## 7. Defect log template

| # | ID (TC-…) | Severity (Blocker/Major/Minor) | What happened | Expected | Evidence | Status |
|---|-----------|-------------------------------|---------------|----------|----------|--------|
| 1 | | | | | | Open/Fixed/Verified |