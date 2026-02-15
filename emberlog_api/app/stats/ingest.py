"""Trunk Recorder ingest placeholders for future stories."""

import json
import logging

from emberlog_api.app.stats import store


log = logging.getLogger("emberlog_api.stats.ingest")
DEFAULT_SOURCE_ID = "trunkrecorder-default"


def resolve_source_id(payload: dict[str, object]) -> str:
    """Resolve source identifier from payload with Story 3 fallback."""
    instance_id = payload.get("instanceId")
    if isinstance(instance_id, str) and instance_id.strip():
        return instance_id
    return DEFAULT_SOURCE_ID


def handle_stats_ws_connected(source_id: str) -> None:
    """Track and log source connection events."""
    store.mark_source_connected(source_id=source_id)
    log.info("stats_ws_connected source_id=%s", source_id)


def handle_stats_ws_message(message_text: str) -> str | None:
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

    log.info(
        "stats_ws_message_received type=%s source_id=%s instance_key=%s",
        type_value,
        source_id,
        instance_key_value,
    )
    store.mark_source_seen(source_id=source_id)
    return source_id


def handle_stats_ws_disconnected(
    source_id: str,
    close_code: int | None = None,
    close_reason: str | None = None,
) -> None:
    """Track and log source disconnection events."""
    store.mark_source_disconnected(source_id=source_id)
    log.info(
        "stats_ws_disconnected source_id=%s close_code=%s close_reason=%s",
        source_id,
        close_code,
        close_reason or "",
    )
