# Versa Director Version Matrix — 22.1.3 / 22.1.4

Both releases are **pre-23.1.1**. They share the same Northbound REST API protocol.
The 23.1.1+ releases changed the OAuth token flow; this application uses a single
`VersaDirectorPre23Client` implementation that covers both 22.1.3 and 22.1.4.

---

## Shared Protocol Facts

| Fact | Detail |
|------|--------|
| API port (Basic Auth) | 9182 |
| API port (OAuth) | 9183 |
| Auth recommendation | OAuth (`POST /auth/token`) over Basic Auth |
| Token endpoint | `POST /auth/token` body: `client_id`, `client_secret`, `username`, `password`, `grant_type=password` |
| API header | `Authorization: Bearer <access-token>` |
| Swagger URL | `https://<director>:9182/docs/swagger-ui.html` (pre-23.1.1 path) |

---

## Candidate Credential Operations (to verify in lab)

### 1. User Management API — `changePassword`

```http
POST /vnms/users/user/change-password
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `username` | string | yes | |
| `current-password` | string | no* | *May be required depending on permissions/model |
| `new-password` | string | yes | |

**Verification required:**
- Does this operate on VOS local users (device users) or Director console users?
- Does template/configuration ownership override the push?
- Required permissions / RBAC on the Director console account?
- Error shape on 22.1.3 vs 22.1.4?

### 2. Secure Access API — `setLocalUserPassword`

```http
POST /vnms/secure/access/localuser/password
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `regtoken` | query | yes | |

**Verification required:**
- When is this the correct mechanism vs `changePassword`?
- What is the regtoken, and who holds it?

---

## Compatibility Matrix

| Operation | 22.1.3 | 22.1.4 | Notes |
|-----------|--------|--------|-------|
| List organisations (`GET /vnms/organization/orgs`) | ✅ expected | ✅ expected | Verified in Swagger (published docs) |
| List devices (`GET /vnms/sdwan/vnf/cpes`) | ✅ expected | ✅ expected | Verified in Swagger |
| Get device status | ✅ expected | ✅ expected | |
| `POST /vnms/users/user/change-password` | **TO VERIFY** | **TO VERIFY** | Lab required |
| `POST /vnms/secure/access/localuser/password` | **TO VERIFY** | **TO VERIFY** | Lab required; clarify regtoken |
| Config ownership / template override effect | **TO VERIFY** | **TO VERIFY** | Critical for rotation safety |

---

## Required Lab Test Environment (Phase 4)

1. Test Versa Director **22.1.3** with read-only admin / API account.
2. Test Versa Director **22.1.4** with read-only admin / API account.
3. Two test CPEs (one per Director, in a **non-production organisation**).
4. A non-production template set where configuration ownership is known.
5. Network path from Docker host to each Director on ports 9182/9183.

---

## References

- [Versa Director REST API Overview (learn.versa-networks.com)](https://learn.versa-networks.com/docs/api-director-getting-started)
- [User Management API — changePassword](https://learn.versa-networks.com/docs/api-director-user-management-api)
- [Secure Access API — setLocalUserPassword](https://learn.versa-networks.com/docs/api-director-secure-access-api)
- [OAuth Client Management](https://learn.versa-networks.com/docs/api-director-oauth-client-management-apis)