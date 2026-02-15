"""Trunk Recorder ingest placeholders for future stories."""

import json
import logging
from dataclasses import dataclass

from emberlog_api.app.stats import store


log = logging.getLogger("emberlog_api.stats.ingest")
DEFAULT_SOURCE_ID = "trunkrecorder-default"


@dataclass(slots=True)
class StatsWsMessageMeta:
    """Parsed metadata for one Trunk Recorder websocket message."""

    source_id: str
    message_type: str
    instance_key: str


def resolve_source_id(payload: dict[str, object]) -> str:
    """Resolve source identifier from payload with Story 3 fallback."""
    instance_id = payload.get("instanceId")
    if isinstance(instance_id, str) and instance_id.strip():
        return instance_id
    return DEFAULT_SOURCE_ID


def handle_stats_ws_connected(source_id: str) -> None:
    """Track and log source connection events."""
    store.mark_source_connected(source_id=source_id)


def handle_stats_ws_message(message_text: str) -> StatsWsMessageMeta | None:
    """Parse one WS text frame and update minimal source status for valid JSON."""
    try:
        payload = json.loads(message_text)
    except json.JSONDecodeError as exc:
        log.warning("stats_ws_invalid_json reason=%s", exc.msg)
        return None

    if not isinstance(payload, dict):
        log.warning("stats_ws_invalid_payload reason=expected_object")
        return None

    message_type = payload.get("type")
    type_value = message_type if isinstance(message_type, str) else "unknown"
    source_id = resolve_source_id(payload)
    instance_key = payload.get("instanceKey")
    instance_key_value = instance_key if isinstance(instance_key, str) else ""

    store.mark_source_seen(source_id=source_id)
    return StatsWsMessageMeta(
        source_id=source_id,
        message_type=type_value,
        instance_key=instance_key_value,
    )


def handle_stats_ws_disconnected(
    source_id: str,
) -> None:
    """Track and log source disconnection events."""
    store.mark_source_disconnected(source_id=source_id)
