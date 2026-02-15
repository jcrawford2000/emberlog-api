"""HTTP routes for stats feature scaffolding."""

import logging

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


log = logging.getLogger("emberlog_api.stats.routes")
router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/systems", response_model=StatsSystemsOut, name="get_stats_systems")
async def get_stats_systems(
    _: None = Depends(require_stats_api_key),
) -> StatsSystemsOut:
    """Story 1 placeholder endpoint for stats systems snapshot."""
    return get_systems_snapshot()


@router.websocket("/trunkrecorder/ws", name="stats_trunkrecorder_ws")
async def stats_trunkrecorder_ws(websocket: WebSocket) -> None:
    """Receive Trunk Recorder stats messages over WebSocket."""
    await websocket.accept()
    current_source_id = DEFAULT_SOURCE_ID
    handle_stats_ws_connected(source_id=current_source_id)

    try:
        while True:
            message_text = await websocket.receive_text()
            source_id = handle_stats_ws_message(message_text=message_text)
            if source_id is not None:
                current_source_id = source_id
    except WebSocketDisconnect as exc:
        handle_stats_ws_disconnected(
            source_id=current_source_id,
            close_code=exc.code,
            close_reason=getattr(exc, "reason", None),
        )
