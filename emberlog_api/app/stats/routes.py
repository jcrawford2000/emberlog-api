"""HTTP routes for stats feature scaffolding."""

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from emberlog_api.app.stats.auth import require_stats_api_key
from emberlog_api.app.stats.ingest import (
    DEFAULT_SOURCE_ID,
    handle_stats_ws_connected,
    handle_stats_ws_disconnected,
    handle_stats_ws_message,
)
from emberlog_api.app.stats.models import StatsSystemsOut
from emberlog_api.app.stats.service import get_systems_snapshot
from emberlog_api.utils.log_context import reset_conn_id, set_conn_id
from emberlog_api.utils.log_safety import payload_preview, redact_headers


log = logging.getLogger("emberlog_api.stats.routes")
router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/systems", response_model=StatsSystemsOut, name="get_stats_systems")
async def get_stats_systems(
    _: None = Depends(require_stats_api_key),
) -> StatsSystemsOut:
    """Story 1 placeholder endpoint for stats systems snapshot."""
    log.info("stats_systems_requested")
    return get_systems_snapshot()


@router.websocket("/trunkrecorder/ws", name="stats_trunkrecorder_ws")
async def stats_trunkrecorder_ws(websocket: WebSocket) -> None:
    """Receive Trunk Recorder stats messages over WebSocket."""
    conn_id = str(uuid4())
    token = set_conn_id(conn_id)
    started = perf_counter()
    client_ip = websocket.client.host if websocket.client else "-"
    log.info(
        "ws_connect path=%s client_ip=%s headers=%s",
        websocket.url.path,
        client_ip,
        redact_headers(dict(websocket.headers)),
    )
    await websocket.accept()
    log.info("ws_accept path=%s client_ip=%s", websocket.url.path, client_ip)
    current_source_id = DEFAULT_SOURCE_ID
    handle_stats_ws_connected(source_id=current_source_id)

    try:
        while True:
            message_text = await websocket.receive_text()
            meta = handle_stats_ws_message(message_text=message_text)
            if meta is not None:
                current_source_id = meta.source_id
                log.info(
                    "ws_message type=%s source_id=%s size_bytes=%s",
                    meta.message_type,
                    meta.source_id,
                    len(message_text.encode("utf-8")),
                )
                preview = payload_preview(message_text)
                if preview:
                    log.debug("ws_message_preview preview=%s", preview)
    except WebSocketDisconnect as exc:
        duration_ms = (perf_counter() - started) * 1000
        log.info(
            "ws_disconnect source_id=%s close_code=%s close_reason=%s duration_ms=%.2f",
            current_source_id,
            exc.code,
            getattr(exc, "reason", "") or "",
            duration_ms,
        )
        handle_stats_ws_disconnected(source_id=current_source_id)
    except Exception as exc:
        duration_ms = (perf_counter() - started) * 1000
        log.exception(
            "ws_error source_id=%s duration_ms=%.2f error=%s",
            current_source_id,
            duration_ms,
            exc,
        )
        raise
    finally:
        reset_conn_id(token)
