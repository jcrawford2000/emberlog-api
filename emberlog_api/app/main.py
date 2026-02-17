import logging

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.api.v1.routers import incidents, sse, traffic
from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.core.lifespan import lifespan
from emberlog_api.utils.loggersetup import configure_logging


configure_logging()
log = logging.getLogger("emberlog_api.app.main")

app = FastAPI(lifespan=lifespan, title="Emberlog API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")
app.include_router(traffic.router, prefix="/api/v1")


async def check_db_connectivity(pool: AsyncConnectionPool) -> bool:
    """Return True when the database accepts a simple query."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@app.get("/healthz")
async def get_healthz() -> dict[str, str]:
    """Liveness endpoint for Kubernetes probes."""
    return {"status": "ok"}


@app.get("/readyz")
async def get_readyz(pool: AsyncConnectionPool = Depends(get_pool)) -> JSONResponse:
    """Readiness endpoint that checks database connectivity."""
    if await check_db_connectivity(pool):
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "reason": "db_unavailable"},
    )
