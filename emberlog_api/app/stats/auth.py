"""Header-based auth helpers for stats routes."""

import logging

from fastapi import HTTPException, Request, status

from emberlog_api.app.core.settings import settings


log = logging.getLogger("emberlog_api.stats.auth")


async def require_stats_api_key(request: Request) -> None:
    """Authorize stats route access with X-API-Key based on runtime settings."""
    expected_api_key = settings.emberlog_api_key.strip()
    runtime_env = settings.emberlog_env.strip().lower()

    if not expected_api_key:
        if runtime_env == "dev":
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    provided_api_key = request.headers.get("X-API-Key", "")
    if provided_api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
