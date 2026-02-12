# Emberlog API — Current State (v0.x)

Last updated: 2026-02-12

## Purpose
`emberlog-api` is a FastAPI service that exposes incident read/write APIs and an SSE stream for incident events.

## Architecture Context
Pipeline (system-level):
Trunk Recorder -> inotify-push -> Calypso (Emberlog Backend) -> Emberlog API -> PostgreSQL -> Emberlog Web

This repo covers **Emberlog API** only.

## Runtime / Stack
- Language: Python 3.12+ (`pyproject.toml`)
- Web framework: FastAPI (`emberlog_api/app/main.py`)
- ASGI server: Uvicorn (invoked by tooling script)
- DB driver/pool: psycopg3 + `psycopg_pool.AsyncConnectionPool` (`emberlog_api/app/db/pool.py`)
- Database: PostgreSQL (external)

## Entrypoints / Startup
- FastAPI app object: `emberlog_api.app.main:app` (`emberlog_api/app/main.py:14`)
- Router mounting:
  - `incidents.router` at `/api/v1` (`emberlog_api/app/main.py:22`)
  - `sse.router` at `/api/v1` (`emberlog_api/app/main.py:23`)
- Local launch pattern in repo tooling:
  - `poetry run uvicorn emberlog_api.app.main:app --host 0.0.0.0 --port 8080 --reload` (`tools/emberlog-api.sh:3`)
- Note: no callable `start` function exists in `emberlog_api.app.main`; `pyproject.toml` script entry appears stale (`pyproject.toml:28`).

## Configuration
Defined in `emberlog_api/app/core/settings.py` via `pydantic-settings`:
- Required:
  - `DATABASE_URL` -> `database_url` (`emberlog_api/app/core/settings.py:9`)
- Optional defaults:
  - `LOG_LEVEL=INFO` -> `log_level` (`emberlog_api/app/core/settings.py:10`)
  - `POOL_MIN_SIZE=1` -> `pool_min_size` (`emberlog_api/app/core/settings.py:11`)
  - `POOL_MAX_SIZE=5` -> `pool_max_size` (`emberlog_api/app/core/settings.py:12`)
- `.env` loading is enabled from repo root (`emberlog_api/app/core/settings.py:14-18`).

## Database / Migrations
- Postgres server provisioning is not handled in app code.
- Shared DB pool is built in `emberlog_api/app/db/pool.py` and opened in lifespan startup (`emberlog_api/app/core/lifespan.py:18-20`).
- Repositories use parameterized SQL with psycopg cursors (`emberlog_api/app/db/repositories/incidents.py`).
- Migrations are SQL scripts under `emberlog_api/migrations/`.
- Alembic config/files are not present in-repo (no `alembic.ini`, no Alembic revision scripts).

## API Surface (Current)
Implemented endpoints:
- `GET /api/v1/incidents/` (paged/filterable list) (`emberlog_api/app/api/v1/routers/incidents.py:26`)
- `GET /api/v1/incidents/{incident_id}` (`emberlog_api/app/api/v1/routers/incidents.py:56`)
- `POST /api/v1/incidents/` (`emberlog_api/app/api/v1/routers/incidents.py:62`)
- `GET /api/v1/sse/incidents` (`emberlog_api/app/api/v1/routers/sse.py:55`)

Missing endpoints:
- `GET /healthz` (not implemented)
- `GET /readyz` (not implemented)

## Auth / Security (Current)
- Auth enforcement: none found in API routers/dependencies.
- CORS is enabled globally with open policy (`allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`) in `emberlog_api/app/main.py:15-20`.
- Rate limiting: none found.

## SSE / Outbox / Notifier
- SSE stream lives in `emberlog_api/app/api/v1/routers/sse.py`.
- Incident creation writes to `incident_outbox` in repository layer (`emberlog_api/app/db/repositories/incidents.py:15-19`, `emberlog_api/app/db/repositories/incidents.py:51-60`).
- Outbox drain loop and delivery router live in `emberlog_api/app/notifier/drain/drain.py`.
- Event-type mapping is configured in lifespan (`"incident.created" -> NotifierClient.on_new_incident`) at `emberlog_api/app/core/lifespan.py:24-29`.
- Notifier client uses `httpx.AsyncClient` with hardcoded base URL `http://localhost:8090` (`emberlog_api/app/notifier/notifier.py:13-15`).

## Observability
- Logging setup is in `emberlog_api/utils/loggersetup.py`.
- Configured handlers:
  - console handler (`StreamHandler`)
  - file handler at `/var/log/emberlog/emberlog_api.log`
- No metrics/tracing instrumentation found in-repo.

## Tests
- Test directory currently contains `tests/test_incidents_list.py`.
- Pattern used:
  - overrides `get_pool` dependency (`tests/test_incidents_list.py:124`)
  - monkeypatches repository function (`tests/test_incidents_list.py:125`)
  - exercises list endpoint filters/pagination via `TestClient`
- Current test run status in this environment:
  - `pytest -q` fails during collection because `httpx` is missing from the active runtime environment, even though declared in `pyproject.toml`.

## Known Gaps / Risks (Observed)
- No health/readiness endpoints yet.
- No in-repo Kubernetes manifests/charts or ArgoCD app config.
- No documented v1.0 security posture (internal-only vs API-key model).
- Notifier endpoint and CORS policy are hardcoded rather than settings-driven.
