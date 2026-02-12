# Emberlog API — Requirements (v1.0)

Last updated: 2026-02-11

## Goal
Deliver `emberlog-api` v1.0 such that it is:
- deployable to Kubernetes via ArgoCD
- configured via environment variables / secrets
- stable and observable enough for daily use
- compatible with the Emberlog pipeline + Web UI

Non-goal: redesigning the pipeline, replacing the DB, or building new major product features.

## Core Requirements (v1.0)

### R1 — Service can run in 3 modes
1. Local dev execution (python/uvicorn)
2. Container execution (docker)
3. Kubernetes execution (Deployment/Service/Ingress)

### R2 — External Postgres integration
- API MUST connect to an externally managed PostgreSQL instance.
- DB connection parameters MUST be provided via env vars.
- Recommended env var:
  - `DATABASE_URL` (preferred), or host/user/password/dbname set.

### R3 — Health + readiness
- Provide liveness endpoint:
  - `GET /healthz` → 200 OK with simple JSON body
- Provide readiness endpoint:
  - `GET /readyz` → 200 OK only when app is ready
  - Readiness SHOULD validate DB connectivity (simple `SELECT 1`) unless too costly.

### R4 — Structured logging
- Log to stdout/stderr.
- Log format SHOULD be JSON in Kubernetes (ideal), but readable text is acceptable in v1.0 if consistent.
- Logs MUST include:
  - timestamp
  - level
  - logger name/module
  - message
- Request logging SHOULD include method/path/status/latency.

### R5 — Configuration
- Config MUST be controllable via env vars (12-factor).
- Include a single authoritative config module (e.g., Pydantic settings).
- Provide documented defaults where safe.

### R6 — Minimal security posture
One of:
- Internal-only (cluster ingress restricted) documented clearly
OR
- API key auth (shared secret) for write endpoints

v1.0 MUST explicitly document which model is used.

### R7 — Kubernetes deployability
Repo MUST include either:
- Helm chart under `charts/emberlog-api/`
OR
- Kustomize manifests under `k8s/base` and `k8s/overlays/<env>`

K8S resources MUST include:
- Deployment
- Service
- Ingress (or equivalent)
- ConfigMap for non-secret config
- Secret references for sensitive config
- Resource requests/limits (reasonable defaults)
- Liveness/readiness probes wired to `/healthz` and `/readyz`

### R8 — ArgoCD integration
- Repo MUST include an ArgoCD Application definition or a standard path consumable by your existing “app of apps” structure.
- Path MUST be documented in README.

### R9 — Test + verification
- Provide at least:
  - unit test smoke coverage for health endpoints
  - minimal DB connectivity test (optional but recommended)
- Provide `DEMO_TEST_PLAN.md` (or README section) to validate end-to-end behavior.


## Out of Scope (v1.0)
- Introducing new infrastructure dependencies (Kafka/Redis/etc.)
- Multi-tenant auth, RBAC, OAuth flows
- Full metrics/tracing platform (nice later)
- Autoscaling policies beyond basic resource limits
