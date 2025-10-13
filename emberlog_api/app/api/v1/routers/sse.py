import asyncio
import json
import logging
import os
import sys
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from emberlog_api.models.incident import IncidentIn, IncidentOut

log = logging.getLogger("emberlog_api.v1.routers.sse")

subscribers: set[asyncio.Queue[str]] = set()

router = APIRouter(prefix="/sse", tags=["sse"])


async def event_generator(queue: asyncio.Queue[str]) -> AsyncIterator[bytes]:
    # Heartbeat every 15s so proxies don't time out
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15)
                log.debug("SSE: New Incident")
                yield f"event: incident\ndata: {msg}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                log.debug("Sending Ping")
                yield b"event: ping\ndata: {}\n\n"
    except asyncio.CancelledError:
        pass


async def publish_incident(incident: IncidentOut):
    log.debug(
        "Publishing: pid=%s subscribers_id=%s size=%d",
        os.getpid(),
        id(subscribers),
        len(subscribers),
    )
    # payload = json.dumps(incident, default=str)
    payload = incident.model_dump_json()
    log.debug("Got incident")
    for q in list(subscribers):
        # don't await put() per subscriber; fan-out without blocking
        try:
            log.debug("Adding Incident to Queue")
            q.put_nowait(payload)
        except asyncio.QueueFull:
            # drop if a client is too slow; EventSource will reconnect later
            pass


@router.get("/incidents")
async def stream_incidents(request: Request):
    log.debug("Adding Subscriber")
    queue: asyncio.Queue[str] = asyncio.Queue()
    subscribers.add(queue)
    log.debug(
        "Subscriber added: pid=%s subscribers_id=%s size=%d",
        os.getpid(),
        id(subscribers),
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
            log.debug(
                "Subscriber removed: pid=%s subscribers_id=%s size=%d",
                os.getpid(),
                id(subscribers),
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
