from fastapi import Request
from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.core.settings import settings


def build_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(
        settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        max_idle=60,
    )


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.pool
