# emberlog-api
Simple Rest API for Emberlog


Create a new branch: feature/dockerfile

Goal:
Add containerization suitable for Kubernetes. Keep it minimal and deterministic.

Requirements:
1) Add Dockerfile at repo root
- Must run the API with uvicorn: emberlog_api.app.main:app
- Listen on port 8080
- Bind host 0.0.0.0
- Set a sensible default log level env var (optional, but do not hardcode secrets)
- Use a non-root user if practical
- Install dependencies via Poetry in a clean way (no dev deps in final image)
- Ensure the image contains only what it needs to run (no test tools)

2) Add .dockerignore
- Exclude .venv, __pycache__, .git, dist/build artifacts, etc.

3) Add minimal documentation
- Update README.md or add docs/CONTAINER.md with:
  - docker build command
  - docker run command including required env vars (DATABASE_URL at least)
  - how to test /healthz and /readyz

Constraints:
- Do not add CI pipelines in this PR.
- Do not add Helm/Kustomize in this PR.
- Do not change application code unless absolutely required to run in a container.
- Do not commit secrets.

Env handling requirements:
- Do NOT bake `.env` into the Docker image.
- Ensure `.dockerignore` excludes `.env`.
- Document running locally using `docker run --env-file .env ...`.
- Add a `.env.example` with placeholder values for required settings (no secrets).

Validation:
- docker build succeeds locally
- docker run works with DATABASE_URL set
- /healthz returns 200
- /readyz returns 200 when DB reachable, 503 otherwise
- poetry run pytest -q still passes on host (no changes should break tests)

Open PR titled: "feat: add Dockerfile for emberlog-api"
Include a short test plan in the PR description.

