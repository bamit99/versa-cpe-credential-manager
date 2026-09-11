# Build: Versa Telecom CPE Credential Manager — MVP

## Context

We are building an internal Telecom Security application to manage unique credentials for a large Versa SD-WAN CPE estate.

Environment:

- Versa SD-WAN / Versa Director 22.x
- Approximately 2,500–3,000 CPEs may exist under a single Director / VD environment
- Requirement: each deployed CPE must have a unique, non-guessable credential
- The application must support controlled credential retrieval by authorised Field Engineers
- Credentials must be securely stored
- All privileged credential access and credential-management activity must be auditable
- We already have CyberArk for Corporate Security, but its use for this Telecom Security solution is NOT decided. Therefore, design the secret-storage layer so that CyberArk can be integrated later without changing the application architecture.
- This is an MVP. Do not build a full PAM replacement.

## Primary MVP Goal

Build a working internal web application that can:

1. Maintain an inventory of Versa CPEs.
2. Associate a unique credential with each CPE.
3. Securely store the actual credential outside the application database.
4. Allow authorised Field Engineers to retrieve the current credential through a responsive web UI on laptop or mobile browser.
5. Support credential rotation.
6. Record a complete audit trail for credential access and changes.
7. Integrate with Versa Director through a dedicated adapter/service layer.
8. Be designed so the secret-storage backend can later be switched between:
   - dedicated Telecom vault
   - CyberArk
   - another enterprise secret-management system

## Important Security Principles

Treat this application as a privileged security system.

Do NOT:

- Store plaintext passwords in PostgreSQL.
- Log passwords or secrets.
- Put passwords into application configuration files.
- Put passwords into source code.
- Return passwords in normal application logs.
- Store secrets in browser local storage.
- Store secrets in JWTs.
- Build custom cryptography when standard, well-reviewed primitives are available.
- Assume CyberArk is available.
- Build a new generic PAM platform.

The database should store metadata and references to secrets, not the actual credentials.

Use secure secret-management abstractions and design the system to support HSM/KMS-backed encryption later.

## Proposed High-Level Architecture

Use a modular architecture similar to:

Web UI
    |
API / Authentication / RBAC
    |
Application Services
    |
+-----------------------+
| CPE Service           |
| Credential Service    |
| Rotation Service      |
| Audit Service         |
| Versa Adapter         |
+-----------------------+
    |
+-------------------------------+
| PostgreSQL                    |
| Secret Store abstraction      |
+-------------------------------+
    |
Versa Director REST/API
    |
Versa CPEs

Do not tightly couple the application to Versa-specific implementation details.

Create a clear interface such as:

    VersaClient
    SecretStore
    CredentialService
    AuditService

The actual implementation of SecretStore must be replaceable.

## Recommended MVP Technology

Choose a modern, maintainable stack with strong security support.

Preferred example:

Backend:
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic

Frontend:
- React
- TypeScript
- responsive design suitable for phone and laptop

Authentication:
- OIDC/OAuth2 compatible architecture
- For initial development, provide a local development authentication mechanism
- Keep production authentication replaceable with corporate SSO/Entra ID/other IdP

Containerisation:
- Docker / Docker Compose for local development

Testing:
- pytest
- API integration tests
- frontend tests
- security-focused tests

You may choose an equivalent stack if there is a compelling reason, but document the choice.

## MVP Features

### 1. CPE Inventory

Create an inventory page showing:

- CPE ID
- Device name
- Serial number
- Site
- Management IP
- Director/VD
- Online/offline status
- Last seen
- Credential status
- Last credential rotation
- Last credential access

Support:

- search
- filtering
- sorting
- pagination

The system must be capable of handling at least 5,000 CPE records without architectural changes.

For the first development version, provide a CSV/mock data importer because the actual Versa environment may not yet be available.

## 2. CPE Detail View

Display:

- CPE identity
- Site
- serial number
- management address
- connectivity status
- credential username
- credential version
- credential status
- last rotation
- last access
- next rotation where applicable

Never display the actual secret by default.

## 3. Credential Generation

Generate cryptographically secure random passwords.

Requirements:

- use a well-tested cryptographic random generator
- configurable length
- avoid predictable patterns
- avoid using CPE metadata
- do not derive passwords from hostname, serial number, site code, IP address, etc.
- do not use reversible deterministic password generation

Make password policy configurable.

For MVP, a strong generated password of approximately 24–32 characters is acceptable unless Versa imposes different constraints.

## 4. Secret Storage

Create a SecretStore interface.

Example:

    class SecretStore:
        create_secret(...)
        get_secret(...)
        update_secret(...)
        delete_secret(...)
        rotate_secret(...)

Provide a DEVELOPMENT implementation only for local testing.

Do not make an insecure plaintext database implementation.

Prefer a local development implementation using a standard secrets backend such as HashiCorp Vault or another well-supported secret manager.

Production implementations should eventually include:

- Telecom Vault
- CyberArk

Do not implement CyberArk yet unless needed for interface validation.

## 5. Credential Retrieval

Field Engineer workflow:

1. Authenticate.
2. Search for CPE.
3. Open CPE.
4. Request credential access.
5. Enter:
   - reason
   - ticket/reference number
6. Backend checks authorisation.
7. Create an audit event.
8. Temporarily reveal the credential.

Credential should:

- be hidden by default
- have a short display timeout
- never be written to logs
- never be cached in browser storage
- be cleared from the UI when the access window expires

Provide:

- Reveal
- Copy
- Hide

For MVP, password visibility may be permitted.

Later versions may support "Connect Without Revealing Password."

## 6. RBAC

Implement at least these roles:

### Administrator

Can:

- manage CPE inventory
- initiate rotation
- view audit records
- manage application configuration

### Security Operator

Can:

- view CPEs
- initiate credential rotations
- view audit events

### Field Engineer

Can:

- view authorised CPEs
- request credential access
- view credentials for authorised devices

Do not allow unrestricted CPE access from the UI.

Implement an authorisation service that can later incorporate:

- region
- site
- team
- assignment
- work order
- ticket

For MVP, a simple user-to-CPE assignment model is sufficient.

## 7. Audit Logging

Every sensitive operation must generate an audit event.

At minimum record:

- timestamp
- authenticated user
- user role
- action
- CPE
- ticket/reference
- reason
- source IP where available
- user-agent/device information where appropriate
- success/failure
- correlation ID

Examples:

    CREDENTIAL_VIEW_REQUESTED
    CREDENTIAL_VIEWED
    CREDENTIAL_GENERATED
    CREDENTIAL_ROTATION_REQUESTED
    CREDENTIAL_ROTATION_STARTED
    CREDENTIAL_ROTATION_SUCCEEDED
    CREDENTIAL_ROTATION_FAILED
    CPE_IMPORTED
    CPE_UPDATED
    ACCESS_DENIED

NEVER record the secret itself.

Audit records should be append-oriented and difficult for normal users to modify or delete.

## 8. Credential Rotation Engine

Implement rotation as a state machine.

Example:

    ACTIVE
       |
       v
    ROTATION_REQUESTED
       |
       v
    NEW_SECRET_GENERATED
       |
       v
    PUSH_TO_CPE
       |
       v
    VERIFY_NEW_CREDENTIAL
       |
       +------ FAIL ------> ROTATION_FAILED
       |
       PASS
       |
       v
    NEW_SECRET_ACTIVE
       |
       v
    OLD_SECRET_RETIRED

Critical rule:

If pushing the new credential fails or verification fails, do NOT replace the active vault reference.

The old credential must remain the known-good credential.

Support:

- single-device rotation
- bulk rotation request

Bulk rotation must have bounded concurrency and retry handling.

Do not blindly attempt 3,000 simultaneous operations.

## 9. Versa Integration

Create a dedicated `versa` module.

Do not scatter Versa API calls throughout the application.

Provide:

- connection configuration
- authentication abstraction
- device discovery
- device status
- credential update operation
- credential verification operation

Initially support a MOCK Versa provider.

Example:

    VersaClient
        -> MockVersaClient
        -> VersaDirector22Client

The application must be fully testable without a live Versa Director.

IMPORTANT:

Before implementing the real credential-change operation, investigate the supported Versa Director 22.x API/CLI mechanism for modifying the relevant local VOS/system-user credential.

Do NOT invent an undocumented endpoint.

Document:

- endpoint or mechanism
- authentication
- expected payload
- response
- error conditions
- whether the operation is supported on the exact 22.x release
- whether Director templates/configuration ownership affects the operation

If the exact Versa mechanism cannot yet be established, implement the interface and mock provider, and clearly mark the Versa operation as TODO rather than creating a fake implementation.

## 10. Director / CPE Synchronisation

Create a sync service capable of:

- importing CPE inventory
- updating status
- detecting newly added CPEs
- detecting removed/decommissioned CPEs
- detecting changes in device metadata

For MVP, provide:

- manual sync
- mock sync

Scheduled background synchronization can come later.

## 11. Dashboard

Create a simple dashboard showing:

- Total CPEs
- Online
- Offline
- Credential healthy
- Credentials needing rotation
- Rotation failures
- Recent privileged access
- Recent rotation activity

Do not over-design this.

## 12. Security Controls

Implement:

- HTTPS-ready deployment
- secure HTTP headers
- CSRF protection where applicable
- input validation
- rate limiting on sensitive endpoints
- authentication timeout
- RBAC checks server-side
- audit logging
- secret redaction
- parameterized database queries
- secure password handling
- no secrets in exceptions/logs

Sensitive operations should require a fresh authentication/session validation where practical.

## 13. Data Model

Initial entities:

User
Role
CPE
Credential
CredentialVersion
AccessRequest
AuditEvent
TicketReference

Example metadata for Credential:

- id
- cpe_id
- username
- secret_reference
- version
- status
- created_at
- activated_at
- retired_at
- last_accessed_at
- last_rotated_at

Again: `secret_reference`, not the password.

## 14. UI/UX

The UI should be functional and security-oriented, not flashy.

Desktop:

- left navigation
- dashboard
- CPE inventory
- CPE details
- rotations
- audit

Mobile:

- responsive layout
- large touch targets
- easy CPE search
- quick credential access
- readable status information

Primary field-engineer workflow should require very few steps.

## 15. Deployment

Provide:

- Dockerfiles
- docker-compose.yml for local development
- `.env.example`
- database migrations
- seed/demo data
- README
- developer setup instructions
- production deployment considerations

Never commit actual secrets.

## 16. Tests

At minimum implement tests covering:

- authentication
- authorisation
- CPE creation/update
- credential generation randomness
- secret-store interactions
- credential retrieval
- credential access authorisation
- audit generation
- successful rotation
- failed rotation
- rollback/retention of old credential after failure
- bulk rotation concurrency
- secret redaction from logs
- RBAC enforcement

Add an explicit automated test that verifies no API response or log entry accidentally contains the stored secret except for the intentionally authorised credential-reveal endpoint.

## 17. Development Approach

Work incrementally.

First build:

Phase 1:
- project skeleton
- database
- authentication mock
- RBAC
- CPE inventory
- secret-store abstraction
- mock vault
- audit logging

Phase 2:
- credential generation
- credential retrieval
- field engineer UI
- rotation state machine

Phase 3:
- mock Versa integration
- synchronisation
- dashboard

Phase 4:
- real Versa Director 22.x integration after confirming the supported mechanism

Do not start with the real Versa API.

The complete MVP must be runnable locally with:

    docker compose up

and should include demo users, demo CPEs and a mock secret backend.

## 18. Future Architecture — DO NOT IMPLEMENT YET

Design interfaces so that these can be added later:

- CyberArk backend
- HSM/KMS-backed secret store
- automatic scheduled rotation
- rotate-on-use
- SSH/session broker
- password-less "Connect to CPE"
- approval workflows
- work-order/ticket integration
- corporate SSO
- SIEM integration
- immutable external audit storage
- multi-Director environments
- HA deployment
- multi-region deployment
- PWA/native mobile application
- PQC/crypto-agility
- advanced reporting

Do not implement these merely because they are mentioned.

## 19. Important Product Principle

This is NOT intended to replace CyberArk or become a general-purpose enterprise PAM product.

The product is a focused:

**Telecom CPE Credential Management and Access Platform**

Its job is to solve the specific operational problem of securely managing thousands of Versa CPE credentials while providing controlled field access and strong auditability.

## Deliverables

Produce:

1. Working source code.
2. Database schema/migrations.
3. Docker development environment.
4. README.
5. Architecture diagram.
6. API documentation.
7. Initial test suite.
8. Threat model for the MVP.
9. List of assumptions.
10. Explicit list of Versa 22.x functionality that has been verified versus functionality that still requires validation.

Before making architectural changes that significantly expand the MVP, stop and document the reason in `DECISIONS.md`.

Keep the implementation intentionally small, modular, secure and extensible.