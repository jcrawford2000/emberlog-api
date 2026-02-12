# Docs/Repo Alignment Report

Date: 2026-02-12
Scope reviewed: `AGENTS.md`, `docs/REQUIREMENTS.md`, `docs/CURRENT_STATE.md`, and repository code.

## A) Repo Snapshot (facts only)

### Entry point(s)
- FastAPI app is created at `emberlog_api/app/main.py:14` as `app = FastAPI(...)`.
- Routers are mounted in `emberlog_api/app/main.py:22` and `emberlog_api/app/main.py:23` with global prefix `/api/v1`.
- Launch command found in tooling script: `poetry run uvicorn emberlog_api.app.main:app ...` at `tools/emberlog-api.sh:3`.
- `pyproject.toml:28` points to `emberlog-api.app.main:start`, but no `start` callable exists in `emberlog_api/app/main.py`.

### Settings/config
- Config is defined with `pydantic-settings` in `emberlog_api/app/core/settings.py:8`.
- Environment-backed settings found:
  - `database_url` (required; maps to `DATABASE_URL`) at `emberlog_api/app/core/settings.py:9`
  - `log_level` default `INFO` at `emberlog_api/app/core/settings.py:10`
  - `pool_min_size` default `1` at `emberlog_api/app/core/settings.py:11`
  - `pool_max_size` default `5` at `emberlog_api/app/core/settings.py:12`
- `.env` loading is enabled via `SettingsConfigDict` at `emberlog_api/app/core/settings.py:14`.

### DB stack
- Uses psycopg3 stack, not asyncpg, via `psycopg_pool.AsyncConnectionPool` in `emberlog_api/app/db/pool.py:2`.
- Pool is built in `emberlog_api/app/db/pool.py:7` and returned from app state in `emberlog_api/app/db/pool.py:16`.
- Pool lifecycle is managed in lifespan (`open` on startup, `close` on shutdown) in `emberlog_api/app/core/lifespan.py:18`, `emberlog_api/app/core/lifespan.py:43`.

### Migrations
- Migration files are SQL scripts under `emberlog_api/migrations/`.
- No Alembic config found (`alembic.ini` absent; no Alembic revision scripts).
- Repo appears to own schema SQL files directly (for example `emberlog_api/migrations/schema_v1.3.2_notification_status.sql:1`).

### Routers and mounted prefixes
- Router module: `emberlog_api/app/api/v1/routers/incidents.py` (`APIRouter(prefix="/incidents")` at `emberlog_api/app/api/v1/routers/incidents.py:23`), mounted at `/api/v1` in `emberlog_api/app/main.py:22`.
- Router module: `emberlog_api/app/api/v1/routers/sse.py` (`APIRouter(prefix="/sse")` at `emberlog_api/app/api/v1/routers/sse.py:17`), mounted at `/api/v1` in `emberlog_api/app/main.py:23`.
- Effective paths include:
  - `GET /api/v1/incidents/`
  - `GET /api/v1/incidents/{incident_id}`
  - `POST /api/v1/incidents/`
  - `GET /api/v1/sse/incidents`

### Auth/CORS
- No auth enforcement dependency/mechanism found in routers (`emberlog_api/app/api/v1/routers/incidents.py`, `emberlog_api/app/api/v1/routers/sse.py`).
- CORS middleware is enabled globally with open policy in `emberlog_api/app/main.py:15` to `emberlog_api/app/main.py:19`.

### SSE/outbox/notifier
- SSE stream implementation: `emberlog_api/app/api/v1/routers/sse.py`.
- Incident creation publishes to in-memory SSE and writes to outbox (`emberlog_api/app/db/repositories/incidents.py:15`, `emberlog_api/app/db/repositories/incidents.py:58`, `emberlog_api/app/api/v1/routers/incidents.py:92`).
- Outbox drain loop + event router: `emberlog_api/app/notifier/drain/drain.py`.
- Event mapping is set in lifespan (`"incident.created" -> nc.on_new_incident`) at `emberlog_api/app/core/lifespan.py:24` to `emberlog_api/app/core/lifespan.py:27`.
- Notifier client uses `httpx.AsyncClient` with hardcoded base URL `http://localhost:8090` in `emberlog_api/app/notifier/notifier.py:13` to `emberlog_api/app/notifier/notifier.py:15`.

### Tests
- Test suite currently has `tests/test_incidents_list.py`.
- Test pattern uses dependency override (`tests/test_incidents_list.py:124`) and monkeypatches repository function (`tests/test_incidents_list.py:125`).
- No health endpoint tests found.
- `pytest -q` currently fails at collection in this environment due missing `httpx` runtime package for `starlette.testclient`.

## B) Conflicts & Gaps

| Doc | Section | Claim | Repo Truth | Severity | Proposed Doc Change |
|---|---|---|---|---|---|
| CURRENT_STATE | Runtime / Stack | DB driver is `asyncpg` | Code uses `psycopg_pool.AsyncConnectionPool` (`emberlog_api/app/db/pool.py:2`) | Major | Replace DB driver text with psycopg3/psycopg_pool. |
| CURRENT_STATE | Database Assumptions | Migrations are Alembic in `emberlog-api/migrations` | SQL migration files exist in `emberlog_api/migrations`; no Alembic config found | Major | Remove Alembic references; state SQL-file migration approach. |
| CURRENT_STATE | API Surface | Incident and SSE routes shown as unchecked/todo | Routes are implemented in `emberlog_api/app/api/v1/routers/incidents.py` and `emberlog_api/app/api/v1/routers/sse.py` | Major | Replace checklist with explicit implemented endpoints and keep health/readiness as missing. |
| CURRENT_STATE | Auth / Security | CORS is unknown | CORS is configured as fully open in `emberlog_api/app/main.py:15-20` | Major | Replace unknown placeholder with exact policy from code. |
| CURRENT_STATE | Repo Layout | Multiple “likely/confirm/TBD” placeholders | Repo has concrete implementations for models, notifier drain, and migrations | Minor | Convert speculative text to confirmed facts and remove placeholders. |
| CURRENT_STATE | Observability | Logging path typo (`emerlog_api/...`) | Actual module path is `emberlog_api/utils/loggersetup.py` | Minor | Fix typo and document configured handlers accurately. |
| REQUIREMENTS | R3 — Health + readiness | Requires `/healthz` and `/readyz` | Neither endpoint exists (`rg "healthz|readyz"` in app code finds none) | Blocker | Keep requirement intact; annotate current status as missing. |
| REQUIREMENTS | R7 — Kubernetes deployability | Requires in-repo Helm/Kustomize + resources | No `k8s/`, `charts/`, or manifests found | Blocker | Keep requirement intact; annotate current status as missing. |
| REQUIREMENTS | R8 — ArgoCD integration | Requires ArgoCD path/definition and README path | No ArgoCD manifests and README has no path details (`README.md:1`) | Blocker | Keep requirement intact; annotate current status as missing. |
| REQUIREMENTS | R9 — Test + verification | Requires health smoke tests + demo validation plan | Only incident list tests exist (`tests/test_incidents_list.py`); no health tests/demo plan found | Major | Keep requirement intact; annotate current status as partial. |
| REQUIREMENTS | R5 — Configuration | Config must be env-controlled | Core settings are env-based, but notifier base URL and CORS are hardcoded (`emberlog_api/app/notifier/notifier.py:14`, `emberlog_api/app/main.py:17-19`) | Major | Keep requirement intact; annotate current status as partial. |
| AGENTS | 3. Database & SQL | Missing explicit note of real DB stack/migration tool | Repo uses psycopg3 + SQL-file migrations, not Alembic | Minor | Add clarifying lines so contributors do not assume asyncpg/Alembic. |
| AGENTS | 8. Outbox / Notifier Rules | “Must be configurable via Settings” (normative), but repo has hardcoded notifier URL | `NotifierClient` hardcodes localhost URL (`emberlog_api/app/notifier/notifier.py:14`) | Major | Add explicit technical-debt note to avoid copying current hardcoded pattern. |

## C) Proposed Doc Patches (unified diffs)

### Patch: `AGENTS.md`
```diff
diff --git a/AGENTS.md b/AGENTS.md
index 1d85452..ec3353f 100644
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -84,9 +84,11 @@ Agents must assume:
 
 Use parameterized SQL with psycopg.
 Never interpolate raw strings.
+Current DB stack in this repo is psycopg3 + psycopg_pool (`AsyncConnectionPool`), not asyncpg pools.
 
 All schema changes must live under:
 emberlog_api/migrations/
+Migrations are maintained as versioned SQL files in this directory (no Alembic config is currently present in-repo).
 
 For new tables or major schema changes:
 Open a separate PR unless explicitly instructed.
@@ -206,6 +208,7 @@ New external integrations:
 - Must use httpx.AsyncClient.
 - Must be configurable via Settings.
 - Must not be hardcoded.
+Current implementation note: `emberlog_api/app/notifier/notifier.py` currently hardcodes a localhost base URL; treat this as technical debt and do not replicate this pattern in new code.
 
 Do NOT modify:
 - Outbox table schema
```

### Patch: `docs/REQUIREMENTS.md`
```diff
diff --git a/docs/REQUIREMENTS.md b/docs/REQUIREMENTS.md
index 58d746f..bb2d9d4 100644
--- a/docs/REQUIREMENTS.md
+++ b/docs/REQUIREMENTS.md
@@ -1,6 +1,6 @@
 # Emberlog API — Requirements (v1.0)
 
-Last updated: 2026-02-11
+Last updated: 2026-02-12
 
 ## Goal
 Deliver `emberlog-api` v1.0 such that it is:
@@ -17,12 +17,14 @@ Non-goal: redesigning the pipeline, replacing the DB, or building new major prod
 1. Local dev execution (python/uvicorn)
 2. Container execution (docker)
 3. Kubernetes execution (Deployment/Service/Ingress)
+Status (repo scan on 2026-02-12): local uvicorn launch path exists; container and Kubernetes deployment assets are not present.
 
 ### R2 — External Postgres integration
 - API MUST connect to an externally managed PostgreSQL instance.
 - DB connection parameters MUST be provided via env vars.
 - Recommended env var:
   - `DATABASE_URL` (preferred), or host/user/password/dbname set.
+Status (repo scan on 2026-02-12): implemented with `DATABASE_URL` via pydantic-settings.
 
 ### R3 — Health + readiness
 - Provide liveness endpoint:
@@ -30,6 +32,7 @@ Non-goal: redesigning the pipeline, replacing the DB, or building new major prod
 - Provide readiness endpoint:
   - `GET /readyz` → 200 OK only when app is ready
   - Readiness SHOULD validate DB connectivity (simple `SELECT 1`) unless too costly.
+Status (repo scan on 2026-02-12): missing; no `/healthz` or `/readyz` routes currently exist.
 
 ### R4 — Structured logging
 - Log to stdout/stderr.
@@ -40,11 +43,13 @@ Non-goal: redesigning the pipeline, replacing the DB, or building new major prod
   - logger name/module
   - message
 - Request logging SHOULD include method/path/status/latency.
+Status (repo scan on 2026-02-12): partial; logging is configured, but request logging and startup DB-readiness summaries are not explicitly implemented.
 
 ### R5 — Configuration
 - Config MUST be controllable via env vars (12-factor).
 - Include a single authoritative config module (e.g., Pydantic settings).
 - Provide documented defaults where safe.
+Status (repo scan on 2026-02-12): partial; central settings module exists, but some runtime values remain hardcoded (for example notifier base URL and CORS policy).
 
 ### R6 — Minimal security posture
 One of:
@@ -53,6 +58,7 @@ OR
 - API key auth (shared secret) for write endpoints
 
 v1.0 MUST explicitly document which model is used.
+Status (repo scan on 2026-02-12): not satisfied; no auth enforcement is present and the deployment security model is not documented in-repo.
 
 ### R7 — Kubernetes deployability
 Repo MUST include either:
@@ -68,16 +74,19 @@ K8S resources MUST include:
 - Secret references for sensitive config
 - Resource requests/limits (reasonable defaults)
 - Liveness/readiness probes wired to `/healthz` and `/readyz`
+Status (repo scan on 2026-02-12): not satisfied; Kubernetes manifests/charts are not present in this repository.
 
 ### R8 — ArgoCD integration
 - Repo MUST include an ArgoCD Application definition or a standard path consumable by your existing “app of apps” structure.
 - Path MUST be documented in README.
+Status (repo scan on 2026-02-12): not satisfied; no ArgoCD manifests/path are present and README does not document one.
 
 ### R9 — Test + verification
 - Provide at least:
   - unit test smoke coverage for health endpoints
   - minimal DB connectivity test (optional but recommended)
 - Provide `DEMO_TEST_PLAN.md` (or README section) to validate end-to-end behavior.
+Status (repo scan on 2026-02-12): partial; tests exist for incident listing, but no health endpoint tests, no DB connectivity verification test, and no demo test plan doc/section were found.
 
 
 ## Out of Scope (v1.0)
```

### Patch: `docs/CURRENT_STATE.md`
```diff
diff --git a/docs/CURRENT_STATE.md b/docs/CURRENT_STATE.md
index 92ea521..fc97747 100644
--- a/docs/CURRENT_STATE.md
+++ b/docs/CURRENT_STATE.md
@@ -1,104 +1,90 @@
 # Emberlog API — Current State (v0.x)
 
-Last updated: 2026-02-11
+Last updated: 2026-02-12
 
 ## Purpose
-`emberlog-api` is the HTTP API layer for Emberlog. It exposes endpoints used by the Emberlog Web UI and other internal services (e.g., ingestion/pipeline components) to read/write data stored in Postgres.
+`emberlog-api` is a FastAPI service that exposes incident read/write APIs and an SSE stream for incident events.
 
 ## Architecture Context
 Pipeline (system-level):
-Trunk Recorder → inotify-push → Calypso (Emberlog Backend) → Emberlog API → PostgreSQL → Emberlog Web
+Trunk Recorder -> inotify-push -> Calypso (Emberlog Backend) -> Emberlog API -> PostgreSQL -> Emberlog Web
 
 This repo covers **Emberlog API** only.
 
 ## Runtime / Stack
-- Language: Python
-- Web framework: FastAPI
-- ASGI server: Uvicorn
-- DB driver: asyncpg 
-- Database: PostgreSQL (external; running on Proxmox)
-
-## Environments
-- Local development: runs against external Postgres (preferred) or developer-provided Postgres.
-- Kubernetes deployment: planned (ArgoCD), secrets strategy TBD (K8S Secrets vs Doppler vs other).
-
-## Database Assumptions
-- Postgres exists and is managed outside this repo.
-- The API **does not** provision the database server.
-- Credentials are provided via environment variables and/or injected secrets.
-- Schema/migrations: 
-  - This repo owns migrations (Alembic), which are defined in `emberlog-api/migrations`
+- Language: Python 3.12+ (`pyproject.toml`)
+- Web framework: FastAPI (`emberlog_api/app/main.py`)
+- ASGI server: Uvicorn (invoked by tooling script)
+- DB driver/pool: psycopg3 + `psycopg_pool.AsyncConnectionPool` (`emberlog_api/app/db/pool.py`)
+- Database: PostgreSQL (external)
+
+## Entrypoints / Startup
+- FastAPI app object: `emberlog_api.app.main:app` (`emberlog_api/app/main.py:14`)
+- Router mounting:
+  - `incidents.router` at `/api/v1` (`emberlog_api/app/main.py:22`)
+  - `sse.router` at `/api/v1` (`emberlog_api/app/main.py:23`)
+- Local launch pattern in repo tooling:
+  - `poetry run uvicorn emberlog_api.app.main:app --host 0.0.0.0 --port 8080 --reload` (`tools/emberlog-api.sh:3`)
+- Note: no callable `start` function exists in `emberlog_api.app.main`; `pyproject.toml` script entry appears stale (`pyproject.toml:28`).
+
+## Configuration
+Defined in `emberlog_api/app/core/settings.py` via `pydantic-settings`:
+- Required:
+  - `DATABASE_URL` -> `database_url` (`emberlog_api/app/core/settings.py:9`)
+- Optional defaults:
+  - `LOG_LEVEL=INFO` -> `log_level` (`emberlog_api/app/core/settings.py:10`)
+  - `POOL_MIN_SIZE=1` -> `pool_min_size` (`emberlog_api/app/core/settings.py:11`)
+  - `POOL_MAX_SIZE=5` -> `pool_max_size` (`emberlog_api/app/core/settings.py:12`)
+- `.env` loading is enabled from repo root (`emberlog_api/app/core/settings.py:14-18`).
+
+## Database / Migrations
+- Postgres server provisioning is not handled in app code.
+- Shared DB pool is built in `emberlog_api/app/db/pool.py` and opened in lifespan startup (`emberlog_api/app/core/lifespan.py:18-20`).
+- Repositories use parameterized SQL with psycopg cursors (`emberlog_api/app/db/repositories/incidents.py`).
+- Migrations are SQL scripts under `emberlog_api/migrations/`.
+- Alembic config/files are not present in-repo (no `alembic.ini`, no Alembic revision scripts).
 
 ## API Surface (Current)
+Implemented endpoints:
+- `GET /api/v1/incidents/` (paged/filterable list) (`emberlog_api/app/api/v1/routers/incidents.py:26`)
+- `GET /api/v1/incidents/{incident_id}` (`emberlog_api/app/api/v1/routers/incidents.py:56`)
+- `POST /api/v1/incidents/` (`emberlog_api/app/api/v1/routers/incidents.py:62`)
+- `GET /api/v1/sse/incidents` (`emberlog_api/app/api/v1/routers/sse.py:55`)
 
-- Health endpoints:
-  - [ ] Currently, no health endpoints exists.  This is a near-term roadmap item.
-
-- Domain endpoints:
-  - [ ] POST `/api/v1/incidents` : Creates New Incident 
-  - [ ] GET `/api/v1/incidents` : Get Incidents (paged)
-  - [ ] GET `/api/v1/incidents/{id}` : Get Incident by ID
-  - [ ] GET `/api/v1/sse/incidents` : Create SSE stream for incidents
+Missing endpoints:
+- `GET /healthz` (not implemented)
+- `GET /readyz` (not implemented)
 
 ## Auth / Security (Current)
-- Authentication mechanism: 
-  - [ ] Not currently implemented.  This is a near-term roadmap item.
-- CORS policy: (unknown.  Add to roadmap)
-- Rate limiting: (none in v0.x)
-
-## Observability (Current)
-- Logging: 
-    - Formatted file and console logging as defined in `emerlog_api/utils/loggersetup.py` and `emberlog_api/utils/logging_filters.py`
-- Metrics: none 
-- Tracing: none 
-
-## Repo Layout (Current)
-
-- `emberlog_api/`
-  - Primary Python package for the Emberlog API service.
-
-- `emberlog_api/app/`
-  - Application layer (FastAPI app, configuration, routing, service wiring).
-  - `app/api/v1/routers/`
-    - Versioned API routers (v1). This is where endpoint route modules live and are composed into the main app.
-  - `app/core/`
-    - Core application concerns (configuration/settings, logging setup, security/auth helpers, dependency injection, constants).
-  - `app/db/`
-    - Database integration layer (connection/session management and DB utilities).
-    - `app/db/repositories/`
-      - Repository pattern implementations for Postgres access (query logic and persistence isolated from routers).
-  - `app/notifier/`
-    - Notifier integration (publishing events/notifications).
-    - `app/notifier/drain/`
-      - Drain/queue/outbox-like components (exact behavior TBD; confirm how notifications are buffered/dispatched).
-
-- `emberlog_api/models/`
-  - Data models used by the API.
-  - (Likely includes Pydantic request/response schemas and/or ORM models; confirm which.)
-
-- `emberlog_api/migrations/`
-  - Database migrations (likely Alembic). This indicates the API repo owns schema evolution (confirm).
-
-- `emberlog_api/utils/`
-  - Shared utility helpers (pure functions, formatting, common helpers).
-
-- `docs/`
-  - Project documentation (architecture notes, API docs, runbooks, etc.).
-
-- `tests/`
-  - Automated tests (unit/integration). Structure may mirror `app/` layout.
-
-- `tools/`
-  - Developer tooling/scripts (local setup helpers, lint scripts, migration helpers, etc.).
-
-## Known Gaps / Risks
-- Kubernetes deployment artifacts not present yet (manifests/Helm/Kustomize).
-- Secrets management approach for K3S not decided.
-- Health/readiness endpoints missing.
-
-## What “v1.0 Current State” should include
-Once we complete v1.0, this doc should be updated to include:
-- exact endpoint list
-- auth model
-- runtime config variables
-- deployment approach (Helm/Kustomize) and ArgoCD path
+- Auth enforcement: none found in API routers/dependencies.
+- CORS is enabled globally with open policy (`allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`) in `emberlog_api/app/main.py:15-20`.
+- Rate limiting: none found.
+
+## SSE / Outbox / Notifier
+- SSE stream lives in `emberlog_api/app/api/v1/routers/sse.py`.
+- Incident creation writes to `incident_outbox` in repository layer (`emberlog_api/app/db/repositories/incidents.py:15-19`, `emberlog_api/app/db/repositories/incidents.py:51-60`).
+- Outbox drain loop and delivery router live in `emberlog_api/app/notifier/drain/drain.py`.
+- Event-type mapping is configured in lifespan (`"incident.created" -> NotifierClient.on_new_incident`) at `emberlog_api/app/core/lifespan.py:24-29`.
+- Notifier client uses `httpx.AsyncClient` with hardcoded base URL `http://localhost:8090` (`emberlog_api/app/notifier/notifier.py:13-15`).
+
+## Observability
+- Logging setup is in `emberlog_api/utils/loggersetup.py`.
+- Configured handlers:
+  - console handler (`StreamHandler`)
+  - file handler at `/var/log/emberlog/emberlog_api.log`
+- No metrics/tracing instrumentation found in-repo.
+
+## Tests
+- Test directory currently contains `tests/test_incidents_list.py`.
+- Pattern used:
+  - overrides `get_pool` dependency (`tests/test_incidents_list.py:124`)
+  - monkeypatches repository function (`tests/test_incidents_list.py:125`)
+  - exercises list endpoint filters/pagination via `TestClient`
+- Current test run status in this environment:
+  - `pytest -q` fails during collection because `httpx` is missing from the active runtime environment, even though declared in `pyproject.toml`.
+
+## Known Gaps / Risks (Observed)
+- No health/readiness endpoints yet.
+- No in-repo Kubernetes manifests/charts or ArgoCD app config.
+- No documented v1.0 security posture (internal-only vs API-key model).
+- Notifier endpoint and CORS policy are hardcoded rather than settings-driven.
```
