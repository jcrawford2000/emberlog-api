# Container Runbook

## Build
```bash
docker build -t emberlog-api:local .
```

## Run
`DATABASE_URL` is required. Do not bake `.env` into the image; pass it at runtime.

```bash
docker run --rm -p 8080:8080 --env-file .env emberlog-api:local
```

You can also provide only required values directly:

```bash
docker run --rm -p 8080:8080 \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/emberlog \
  emberlog-api:local
```

Use `.env.example` as a template for local `.env` values.

## Probe Checks
```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
```

- `/healthz` should return `200` with `{"status":"ok"}`.
- `/readyz` returns:
  - `200` with `{"status":"ok"}` when DB is reachable.
  - `503` with `{"status":"not_ready","reason":"db_unavailable"}` when DB is not reachable.
