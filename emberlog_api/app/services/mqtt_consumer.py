from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.core.settings import settings
from emberlog_api.app.db.repositories import traffic as traffic_repo

log = logging.getLogger("emberlog_api.services.mqtt_consumer")

RATES_TOPIC_SUFFIX = "rates"
RECORDERS_TOPIC_SUFFIX = "recorders"
CALLS_ACTIVE_TOPIC_SUFFIX = "calls_active"


def _topic(topic_suffix: str) -> str:
    return f"{settings.mqtt_topic_prefix}/{topic_suffix}"


def _updated_at_from_timestamp(timestamp: Any) -> datetime:
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)


def _decode_rate_pct(decoderate: float) -> float:
    return decoderate * 100.0 if decoderate <= 1.0 else decoderate


async def handle_rates_message(pool: AsyncConnectionPool, payload: dict[str, Any]) -> None:
    """Process a rates payload and upsert latest per-system decode rates."""
    instance_id = str(payload["instance_id"])
    updated_at = _updated_at_from_timestamp(payload["timestamp"])
    rates = payload.get("rates")
    if not isinstance(rates, list):
        log.error("rates payload missing list field", extra={"instance_id": instance_id})
        return

    for item in rates:
        if not isinstance(item, dict):
            log.error("rates item is not an object", extra={"instance_id": instance_id})
            continue

        try:
            decoderate_raw = float(item["decoderate"])
            decoderate_pct = _decode_rate_pct(decoderate_raw)
            control_channel = item.get("control_channel")
            control_channel_hz = (
                int(control_channel) if control_channel is not None else None
            )

            await traffic_repo.upsert_decode_rate(
                pool,
                instance_id=instance_id,
                sys_num=int(item["sys_num"]),
                sys_name=str(item["sys_name"]),
                decoderate_raw=decoderate_raw,
                decoderate_pct=decoderate_pct,
                decoderate_interval_s=(
                    float(item["decoderate_interval"])
                    if item.get("decoderate_interval") is not None
                    else None
                ),
                control_channel_hz=control_channel_hz,
                updated_at=updated_at,
            )
            log.debug(
                "processed rates message",
                extra={
                    "instance_id": instance_id,
                    "sys_name": str(item["sys_name"]),
                    "decode_rate_pct": decoderate_pct,
                },
            )
        except Exception:
            log.exception(
                "failed to upsert decode rate",
                extra={"instance_id": instance_id, "rate_item": item},
            )


async def handle_recorders_message(
    pool: AsyncConnectionPool, payload: dict[str, Any]
) -> None:
    """Process a recorders payload and upsert latest recorder snapshot."""
    instance_id = str(payload["instance_id"])
    updated_at = _updated_at_from_timestamp(payload["timestamp"])
    recorders = payload.get("recorders")
    if not isinstance(recorders, list):
        log.error(
            "recorders payload missing list field", extra={"instance_id": instance_id}
        )
        return

    total_count = len(recorders)
    recording_count = sum(
        1
        for rec in recorders
        if isinstance(rec, dict) and rec.get("rec_state_type") == "RECORDING"
    )
    idle_count = sum(
        1
        for rec in recorders
        if isinstance(rec, dict) and rec.get("rec_state_type") == "IDLE"
    )
    available_count = sum(
        1
        for rec in recorders
        if isinstance(rec, dict) and rec.get("rec_state_type") == "AVAILABLE"
    )

    try:
        await traffic_repo.upsert_recorders_snapshot(
            pool,
            instance_id=instance_id,
            recorders_json=payload,
            total_count=total_count,
            recording_count=recording_count,
            idle_count=idle_count,
            available_count=available_count,
            updated_at=updated_at,
        )
        log.debug(
            "processed recorders message",
            extra={"instance_id": instance_id, "total_count": total_count},
        )
    except Exception:
        log.exception("failed to upsert recorders snapshot", extra={"instance_id": instance_id})


async def handle_calls_active_message(
    pool: AsyncConnectionPool, payload: dict[str, Any]
) -> None:
    """Process a calls_active payload and upsert latest active-calls snapshot."""
    instance_id = str(payload["instance_id"])
    updated_at = _updated_at_from_timestamp(payload["timestamp"])
    calls = payload.get("calls")
    if not isinstance(calls, list):
        log.error(
            "calls_active payload missing list field", extra={"instance_id": instance_id}
        )
        return

    active_calls_count = len(calls)

    try:
        await traffic_repo.upsert_calls_active_snapshot(
            pool,
            instance_id=instance_id,
            calls_json=payload,
            active_calls_count=active_calls_count,
            updated_at=updated_at,
        )
        log.debug(
            "processed calls_active message",
            extra={
                "instance_id": instance_id,
                "active_calls_count": active_calls_count,
            },
        )
    except Exception:
        log.exception(
            "failed to upsert calls_active snapshot", extra={"instance_id": instance_id}
        )


async def process_mqtt_message(
    pool: AsyncConnectionPool, topic: str, payload_bytes: bytes
) -> None:
    """Parse and dispatch a single MQTT message by topic."""
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        log.exception("failed to parse mqtt message as JSON", extra={"topic": topic})
        return

    if not isinstance(payload, dict):
        log.error("mqtt payload must be a JSON object", extra={"topic": topic})
        return

    try:
        if topic == _topic(RATES_TOPIC_SUFFIX):
            await handle_rates_message(pool, payload)
            return

        if topic == _topic(RECORDERS_TOPIC_SUFFIX):
            await handle_recorders_message(pool, payload)
            return

        if topic == _topic(CALLS_ACTIVE_TOPIC_SUFFIX):
            await handle_calls_active_message(pool, payload)
            return

        log.debug("ignoring mqtt message for unsupported topic", extra={"topic": topic})
    except KeyError:
        log.exception("mqtt payload missing required field", extra={"topic": topic})
    except Exception:
        log.exception("failed processing mqtt message", extra={"topic": topic})


async def start_mqtt_consumer(pool: AsyncConnectionPool) -> None:
    """Run a reconnecting MQTT consumer loop for Traffic Monitor topics."""
    try:
        from aiomqtt import Client, MqttError
    except Exception:
        log.exception("aiomqtt is not available; mqtt consumer cannot start")
        return

    reconnect_delay_s = 1.0
    max_reconnect_delay_s = 60.0
    topics = [
        _topic(RATES_TOPIC_SUFFIX),
        _topic(RECORDERS_TOPIC_SUFFIX),
        _topic(CALLS_ACTIVE_TOPIC_SUFFIX),
    ]

    while True:
        try:
            async with Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            ) as client:
                log.info(
                    "connected to mqtt broker",
                    extra={
                        "host": settings.mqtt_host,
                        "port": settings.mqtt_port,
                        "topic_prefix": settings.mqtt_topic_prefix,
                    },
                )
                reconnect_delay_s = 1.0

                for topic in topics:
                    await client.subscribe(topic)

                async for message in client.messages:
                    await process_mqtt_message(
                        pool,
                        topic=str(message.topic),
                        payload_bytes=bytes(message.payload),
                    )

        except asyncio.CancelledError:
            log.info("mqtt consumer stopped")
            raise
        except MqttError:
            log.exception("mqtt broker connection error")
        except Exception:
            log.exception("unexpected mqtt consumer failure")

        log.info("mqtt reconnect scheduled", extra={"delay_s": reconnect_delay_s})
        await asyncio.sleep(reconnect_delay_s)
        reconnect_delay_s = min(reconnect_delay_s * 2.0, max_reconnect_delay_s)
