import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.api.v1.routers import incidents, sse
from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.core.lifespan import lifespan
from emberlog_api.app.stats import routes as stats_routes
from emberlog_api.utils.log_context import reset_request_id, set_request_id
from emberlog_api.utils.log_safety import redact_headers
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
app.include_router(stats_routes.router, prefix="/api/v1")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    """Attach request correlation ID and log one structured line per request."""
    started = perf_counter()
    request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid4())
    request.state.request_id = request_id
    token = set_request_id(request_id)

    response: Response | None = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (perf_counter() - started) * 1000
        client_ip = request.client.host if request.client else "-"
        status_code = response.status_code if response is not None else 500
        if response is not None:
            response.headers["X-Request-ID"] = request_id

        log.info(
            "http_request method=%s path=%s status=%s duration_ms=%.2f client_ip=%s",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            client_ip,
        )
        log.debug(
            "http_request_headers method=%s path=%s headers=%s",
            request.method,
            request.url.path,
            redact_headers(dict(request.headers)),
        )
        reset_request_id(token)


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
    log.debug("healthz_checked")
    return {"status": "ok"}


@app.get("/readyz")
async def get_readyz(pool: AsyncConnectionPool = Depends(get_pool)) -> JSONResponse:
    """Readiness endpoint that checks database connectivity."""
    if await check_db_connectivity(pool):
        log.debug("readyz_checked status=ok")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})

    log.warning("readyz_checked status=not_ready reason=db_unavailable")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "reason": "db_unavailable"},
    )
