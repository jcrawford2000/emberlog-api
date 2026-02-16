import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from emberlog_api.app.db.pool import build_pool
from emberlog_api.app.notifier.drain.drain import (
    OutboxDrain,
    OutboxDrainConfig,
    Router,
)
from emberlog_api.app.notifier.notifier import NotifierClient
from emberlog_api.app.services.mqtt_consumer import start_mqtt_consumer


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
    mqtt_task = asyncio.create_task(start_mqtt_consumer(pool))
    app.state.mqtt_task = mqtt_task

    try:
        # 4) hand control to FastAPI
        yield
    finally:
        # 5) stop drain first, then close pool
        mqtt_task.cancel()
        try:
            await mqtt_task
        except asyncio.CancelledError:
            pass
        await drain.stop()
        await pool.close()
