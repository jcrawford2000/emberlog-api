from contextlib import asynccontextmanager

from fastapi import FastAPI

from emberlog_api.app.db.pool import build_pool
from emberlog_api.app.notifier.drain.drain import (
    OutboxDrain,
    OutboxDrainConfig,
    Router,
    handle_incident_created,
)
from emberlog_api.app.notifier.notifier import NotifierClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) open shared DB pool
    pool = build_pool()
    await pool.open(wait=True)
    app.state.pool = pool
    nc = NotifierClient()

    # 2) build router (map event types -> handlers)
    router = Router(
        {
            "incident.created": nc.on_new_incident,
            # add more handlers here when ready
        }
    )

    # 3) start the drain
    outboxConfig = OutboxDrainConfig(pool=pool)
    drain = OutboxDrain(cfg=outboxConfig, router=router)
    await drain.start()
    app.state.drain = drain

    try:
        # 4) hand control to FastAPI
        yield
    finally:
        # 5) stop drain first, then close pool
        await drain.stop()
        await pool.close()
