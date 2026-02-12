FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    LOG_LEVEL=INFO \
    ENABLE_FILE_LOGGING=false

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /app/.venv /app/.venv
COPY emberlog_api ./emberlog_api

EXPOSE 8080

USER app

CMD ["uvicorn", "emberlog_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
