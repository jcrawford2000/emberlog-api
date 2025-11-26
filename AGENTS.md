Guidelines for AI Agents Contributing to Emberlog-API

This document defines how automated agents (e.g., Codex) should interact with this repository.
Follow these rules when generating code, creating branches, writing tests, or opening PRs.

1. Code Style & Structure

Write idiomatic FastAPI, async/await, and typed Python.

Follow existing patterns:

Repositories live under emberlog_api/app/db/repositories.

API routes under emberlog_api/app/api/v1/routers.

Pydantic models under emberlog_api/models.

Core services under emberlog_api/app/....

Maintain consistency with existing naming:

Repository functions: select_foo, insert_foo, list_foo.

Route functions: get_foo, create_foo, etc.

Use type hints everywhere.

Write concise docstrings for all new public functions.

2. Database & SQL

Use parameterized SQL (%(param)s) with psycopg — never interpolate raw strings.

Place schema changes only in emberlog_api/migrations.

For new tables or major schema changes, open a separate PR unless explicitly instructed.

Keep SQL readable and consistent:

Capitalize keywords (SELECT, FROM, WHERE).

Indent multi-line SQL blocks.

3. API Design

All new endpoints must live under /api/v1/....

Always provide:

Pydantic input model (if POST/PUT).

Pydantic output model.

Query parameters explicitly typed (Query(...)).

Follow existing patterns for pagination:

page, page_size → backend must convert to limit/offset.

Document each new endpoint in the PR description.

4. SSE

SSE events should follow existing envelope structures.

Don’t change event formats unless explicitly asked.

If adding new event types:

Update the SSE router in app/api/v1/routers/sse.py.

Add the event type to the outbox handler mapping.

5. Outbox / Notifier

Outbox logic lives in emberlog_api/app/notifier.

If routing new event types:

Update the Router mapping in lifespan.py.

Do not hardcode new HTTP paths; they must be configurable via Settings.

Any new Notifier integration must use httpx.AsyncClient.

6. Configuration

All new service URLs, feature flags, or paths must:

Be added to Settings (pydantic-settings).

Never be hardcoded.

Default configs should be safe for local development.

7. Logging

Use logger = logging.getLogger("emberlog_api.<component>").

Use structured logging where possible.

Avoid excessive debug logs inside tight loops or high-volume handlers.

8. Tests

If modifying repo logic or API endpoints:

Add or update tests in tests/.

Use the existing pattern:

Override get_pool with a fake.

Monkeypatch repository functions when DB isn’t required.

Tests should not depend on a running database unless explicitly requested.

9. Branching & PRs

When creating or modifying code:

Create a feature branch named:

feature/<short-description> or fix/<short-description>

Open PRs with:

A descriptive title.

A summary of changes.

Any required screenshots, logs, or examples.

Never merge without tests passing (if applicable).

10. Ask for Clarification

If a task appears ambiguous or under-specified:

Ask for clarification rather than guessing.

Do not add unrelated changes.

Don’t introduce new architectural concepts without approval.

11. What NOT to change without explicit instructions

SSE event schema

Incident schema

Outbox table schema

Directory structure under emberlog_api/app

Application lifespan behavior

Names of existing public endpoints

12. Philosophy

Emberlog-API follows a simple architecture:

API layer → HTTP routes

Repository layer → SQL + DB access

Outbox → decoupled event dispatch

Notifier → external service integration

SSE → real-time forwarding, not authoritative storage

Database → source of truth

Agents should keep these responsibilities cleanly separated.

13. When in doubt

Prefer small PRs over large ones.

Match existing code.

Ask Glitch (the AI reviewer) to validate design choices.

Don’t invent new patterns unless explicitly asked.
