import asyncio
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from emberlog_api.models.incident import IncidentOut

log = logging.getLogger("emberlog_api.v1.routers.sse")

subscribers: set[asyncio.Queue[str]] = set()

router = APIRouter(prefix="/sse", tags=["sse"])


async def event_generator(queue: asyncio.Queue[str]) -> AsyncIterator[bytes]:
    # Heartbeat every 15s so proxies don't time out
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15)
                yield f"event: incident\ndata: {msg}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                yield b"event: ping\ndata: {}\n\n"
    except asyncio.CancelledError:
        pass


async def publish_incident(incident: IncidentOut):
    payload = incident.model_dump_json()
    for q in list(subscribers):
        # don't await put() per subscriber; fan-out without blocking
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            # drop if a client is too slow; EventSource will reconnect later
            pass


@router.get("/incidents")
async def stream_incidents(request: Request):
    queue: asyncio.Queue[str] = asyncio.Queue()
    subscribers.add(queue)
    client_ip = request.client.host if request.client else "-"
    log.info(
        "sse_connect path=%s client_ip=%s subscribers=%s",
        request.url.path,
        client_ip,
        len(subscribers),
    )

    async def close_when_client_disconnects():
        try:
            # Poll until the client disconnects, THEN remove.
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(1)
        finally:
            subscribers.discard(queue)
            log.info(
                "sse_disconnect path=%s client_ip=%s subscribers=%s",
                request.url.path,
                client_ip,
                len(subscribers),
            )

    asyncio.create_task(close_when_client_disconnects())
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # For Nginx: disable proxy buffering; for Cloudflare, default is OK for SSE
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(queue), media_type="text/event-stream", headers=headers
    )
