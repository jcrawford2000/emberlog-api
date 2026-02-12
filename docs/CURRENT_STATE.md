# Emberlog API — Current State (v0.x)

Last updated: 2026-02-11

## Purpose
`emberlog-api` is the HTTP API layer for Emberlog. It exposes endpoints used by the Emberlog Web UI and other internal services (e.g., ingestion/pipeline components) to read/write data stored in Postgres.

## Architecture Context
Pipeline (system-level):
Trunk Recorder → inotify-push → Calypso (Emberlog Backend) → Emberlog API → PostgreSQL → Emberlog Web

This repo covers **Emberlog API** only.

## Runtime / Stack
- Language: Python
- Web framework: FastAPI
- ASGI server: Uvicorn
- DB driver: asyncpg 
- Database: PostgreSQL (external; running on Proxmox)

## Environments
- Local development: runs against external Postgres (preferred) or developer-provided Postgres.
- Kubernetes deployment: planned (ArgoCD), secrets strategy TBD (K8S Secrets vs Doppler vs other).

## Database Assumptions
- Postgres exists and is managed outside this repo.
- The API **does not** provision the database server.
- Credentials are provided via environment variables and/or injected secrets.
- Schema/migrations: 
  - This repo owns migrations (Alembic), which are defined in `emberlog-api/migrations`

## API Surface (Current)

- Health endpoints:
  - [ ] Currently, no health endpoints exists.  This is a near-term roadmap item.

- Domain endpoints:
  - [ ] POST `/api/v1/incidents` : Creates New Incident 
  - [ ] GET `/api/v1/incidents` : Get Incidents (paged)
  - [ ] GET `/api/v1/incidents/{id}` : Get Incident by ID
  - [ ] GET `/api/v1/sse/incidents` : Create SSE stream for incidents

## Auth / Security (Current)
- Authentication mechanism: 
  - [ ] Not currently implemented.  This is a near-term roadmap item.
- CORS policy: (unknown.  Add to roadmap)
- Rate limiting: (none in v0.x)

## Observability (Current)
- Logging: 
    - Formatted file and console logging as defined in `emerlog_api/utils/loggersetup.py` and `emberlog_api/utils/logging_filters.py`
- Metrics: none 
- Tracing: none 

## Repo Layout (Current)

- `emberlog_api/`
  - Primary Python package for the Emberlog API service.

- `emberlog_api/app/`
  - Application layer (FastAPI app, configuration, routing, service wiring).
  - `app/api/v1/routers/`
    - Versioned API routers (v1). This is where endpoint route modules live and are composed into the main app.
  - `app/core/`
    - Core application concerns (configuration/settings, logging setup, security/auth helpers, dependency injection, constants).
  - `app/db/`
    - Database integration layer (connection/session management and DB utilities).
    - `app/db/repositories/`
      - Repository pattern implementations for Postgres access (query logic and persistence isolated from routers).
  - `app/notifier/`
    - Notifier integration (publishing events/notifications).
    - `app/notifier/drain/`
      - Drain/queue/outbox-like components (exact behavior TBD; confirm how notifications are buffered/dispatched).

- `emberlog_api/models/`
  - Data models used by the API.
  - (Likely includes Pydantic request/response schemas and/or ORM models; confirm which.)

- `emberlog_api/migrations/`
  - Database migrations (likely Alembic). This indicates the API repo owns schema evolution (confirm).

- `emberlog_api/utils/`
  - Shared utility helpers (pure functions, formatting, common helpers).

- `docs/`
  - Project documentation (architecture notes, API docs, runbooks, etc.).

- `tests/`
  - Automated tests (unit/integration). Structure may mirror `app/` layout.

- `tools/`
  - Developer tooling/scripts (local setup helpers, lint scripts, migration helpers, etc.).

## Known Gaps / Risks
- Kubernetes deployment artifacts not present yet (manifests/Helm/Kustomize).
- Secrets management approach for K3S not decided.
- Health/readiness endpoints missing.

## What “v1.0 Current State” should include
Once we complete v1.0, this doc should be updated to include:
- exact endpoint list
- auth model
- runtime config variables
- deployment approach (Helm/Kustomize) and ArgoCD path
