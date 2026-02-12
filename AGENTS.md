# AGENTS.md — Guidelines for AI Agents Contributing to Emberlog-API

This document defines how automated agents (e.g., Codex) must interact with this repository.

The goal is to deliver Emberlog-API v1.0:
- Kubernetes deployable
- ArgoCD compatible
- Configurable via environment variables
- Operationally stable
- Architecturally consistent

Agents must follow these rules when generating code, creating branches, writing tests, or opening PRs.

Source of truth:
- docs/REQUIREMENTS.md defines what v1.0 must achieve.
- docs/CURRENT_STATE.md defines what currently exists.
- If there is a mismatch, do NOT guess — update docs or ask for clarification.


--------------------------------------------------------------------
1. Architecture Principles (Do Not Violate)
--------------------------------------------------------------------

Emberlog-API follows a layered architecture:

API layer → HTTP routes
Repository layer → SQL + DB access
Outbox → decoupled event dispatch
Notifier → external service integration
SSE → real-time forwarding (not storage)
Database → source of truth

Do not blur responsibilities across layers.

Routers must not contain raw SQL.
Repositories must not contain HTTP logic.
Notifier must not contain business logic.


--------------------------------------------------------------------
2. Code Style & Structure
--------------------------------------------------------------------

Write idiomatic FastAPI with async/await and typed Python.

Follow existing layout:

- API routes:
  emberlog_api/app/api/v1/routers/

- Repositories:
  emberlog_api/app/db/repositories/

- Models:
  emberlog_api/models/

- Core services/config:
  emberlog_api/app/core/

- Notifier & outbox:
  emberlog_api/app/notifier/

Naming conventions:
- Repository functions: select_foo, insert_foo, list_foo
- Route functions: get_foo, create_foo, etc.

Use type hints everywhere.
Write concise docstrings for all new public functions.
Prefer explicit code over abstraction.

Do NOT introduce new architectural patterns.


--------------------------------------------------------------------
3. Database & SQL
--------------------------------------------------------------------

Postgres is external and already provisioned.

Agents must assume:
- Database server exists.
- Credentials are injected via environment variables.
- API does NOT provision Postgres.

Use parameterized SQL with psycopg.
Never interpolate raw strings.
Current DB stack in this repo is psycopg3 + psycopg_pool (`AsyncConnectionPool`), not asyncpg pools.

All schema changes must live under:
emberlog_api/migrations/
Migrations are maintained as versioned SQL files in this directory (no Alembic config is currently present in-repo).

For new tables or major schema changes:
Open a separate PR unless explicitly instructed.

Keep SQL readable:
- Capitalize keywords (SELECT, FROM, WHERE).
- Indent multi-line SQL.


--------------------------------------------------------------------
4. Configuration (12-Factor Required)
--------------------------------------------------------------------

All configuration must come from environment variables.

Use pydantic-settings (Settings class).

Never hardcode:
- URLs
- Ports
- Feature flags
- API keys
- Notifier endpoints
- Database credentials

Defaults must be safe for local development.

Kubernetes will provide configuration via:
- ConfigMap (non-secret)
- Secret (sensitive values)

Agents must not commit secrets.


--------------------------------------------------------------------
5. API Design Rules
--------------------------------------------------------------------

All endpoints must live under:

/api/v1/...

Every new endpoint must include:
- Typed query parameters
- Pydantic input model (POST/PUT)
- Pydantic response model
- Clear status codes

Pagination:
- page
- page_size
Backend converts to limit/offset.

Document new endpoints in PR description.

Do NOT:
- Rename existing public endpoints.
- Change request/response schemas.
- Modify Incident schema.
- Modify SSE event schema.


--------------------------------------------------------------------
6. Health & Kubernetes Readiness (v1.0 Requirement)
--------------------------------------------------------------------

v1.0 requires:

- GET /healthz → liveness probe
- GET /readyz → readiness probe

Readiness should confirm DB connectivity if feasible.

Agents must ensure:
- App starts cleanly with missing DB only failing readiness.
- Logging clearly shows startup state.

Kubernetes requirements:
- Deployment
- Service
- Ingress
- Liveness probe
- Readiness probe
- Resource requests/limits
- Secret references

Agents must not introduce Helm AND Kustomize.
Choose one pattern and follow existing cluster conventions.


--------------------------------------------------------------------
7. SSE Rules
--------------------------------------------------------------------

SSE event format is stable and must not change.

If adding new event types:
- Update sse router.
- Update outbox handler mapping.
- Maintain envelope structure.

SSE is forward-only streaming.
It is not storage.


--------------------------------------------------------------------
8. Outbox / Notifier Rules
--------------------------------------------------------------------

Outbox logic lives in:
emberlog_api/app/notifier/

If routing new event types:
- Update Router mapping in lifespan.py.

New external integrations:
- Must use httpx.AsyncClient.
- Must be configurable via Settings.
- Must not be hardcoded.
Current implementation note: `emberlog_api/app/notifier/notifier.py` currently hardcodes a localhost base URL; treat this as technical debt and do not replicate this pattern in new code.

Do NOT modify:
- Outbox table schema
- Application lifespan behavior


--------------------------------------------------------------------
9. Logging & Observability
--------------------------------------------------------------------

Use:

logger = logging.getLogger("emberlog_api.<component>")

Log to stdout.

Structured logging preferred.
Avoid excessive debug logs in high-volume paths.

Never use print().

Startup logs must:
- Show configuration summary (without secrets)
- Indicate DB connectivity status


--------------------------------------------------------------------
10. Testing Rules
--------------------------------------------------------------------

If modifying:
- repository logic
- API endpoints
- configuration behavior

You must add or update tests.

Use existing patterns:
- Override get_pool with a fake.
- Monkeypatch repository functions.
- Tests must not require a running DB unless explicitly requested.

Minimum v1.0 coverage:
- health endpoints
- config validation
- route smoke tests


--------------------------------------------------------------------
11. Branching & PRs
--------------------------------------------------------------------

Create branches:

feature/<short-description>
fix/<short-description>

PR must include:
- Summary of changes
- Why change was required
- How to validate (commands)
- Any API contract changes

Keep PRs small.
Prefer iterative changes over sweeping refactors.

Do not merge without tests passing.


--------------------------------------------------------------------
12. Deployment & ArgoCD Awareness
--------------------------------------------------------------------

v1.0 must be deployable via ArgoCD.

Agents must:
- Keep containerization simple.
- Avoid adding infrastructure dependencies.
- Ensure app works in:
  - local mode
  - container mode
  - Kubernetes mode

Do not:
- Add Redis/Kafka/etc.
- Introduce background schedulers without approval.
- Modify cluster-wide resources.


--------------------------------------------------------------------
13. What NOT to Change Without Explicit Instruction
--------------------------------------------------------------------

- SSE schema
- Incident schema
- Outbox table schema
- Directory structure under emberlog_api/app
- Application lifespan behavior
- Public endpoint names


--------------------------------------------------------------------
14. When in Doubt
--------------------------------------------------------------------

If ambiguous:
- Ask for clarification.
- Do not guess.
- Do not invent new patterns.

Prefer:
- Small PRs
- Explicit code
- Matching existing style

Glitch (AI reviewer) should validate architecture decisions before major changes.
