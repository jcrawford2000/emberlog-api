from datetime import datetime

from psycopg.types.json import Json
from psycopg_pool import AsyncConnectionPool

SQL_UPSERT_DECODE_RATE = """
INSERT INTO tr_decode_rate_latest (
    instance_id,
    sys_num,
    sys_name,
    decoderate_raw,
    decoderate_pct,
    decoderate_interval_s,
    control_channel_hz,
    updated_at
)
VALUES (
    %(instance_id)s,
    %(sys_num)s,
    %(sys_name)s,
    %(decoderate_raw)s,
    %(decoderate_pct)s,
    %(decoderate_interval_s)s,
    %(control_channel_hz)s,
    %(updated_at)s
)
ON CONFLICT (instance_id, sys_num) DO UPDATE
SET
    sys_name = EXCLUDED.sys_name,
    decoderate_raw = EXCLUDED.decoderate_raw,
    decoderate_pct = EXCLUDED.decoderate_pct,
    decoderate_interval_s = EXCLUDED.decoderate_interval_s,
    control_channel_hz = EXCLUDED.control_channel_hz,
    updated_at = EXCLUDED.updated_at
"""

SQL_UPSERT_RECORDERS_SNAPSHOT = """
INSERT INTO tr_recorders_snapshot_latest (
    instance_id,
    recorders_json,
    total_count,
    recording_count,
    idle_count,
    available_count,
    updated_at
)
VALUES (
    %(instance_id)s,
    %(recorders_json)s,
    %(total_count)s,
    %(recording_count)s,
    %(idle_count)s,
    %(available_count)s,
    %(updated_at)s
)
ON CONFLICT (instance_id) DO UPDATE
SET
    recorders_json = EXCLUDED.recorders_json,
    total_count = EXCLUDED.total_count,
    recording_count = EXCLUDED.recording_count,
    idle_count = EXCLUDED.idle_count,
    available_count = EXCLUDED.available_count,
    updated_at = EXCLUDED.updated_at
"""

SQL_UPSERT_CALLS_ACTIVE_SNAPSHOT = """
INSERT INTO tr_calls_active_snapshot_latest (
    instance_id,
    calls_json,
    active_calls_count,
    updated_at
)
VALUES (
    %(instance_id)s,
    %(calls_json)s,
    %(active_calls_count)s,
    %(updated_at)s
)
ON CONFLICT (instance_id) DO UPDATE
SET
    calls_json = EXCLUDED.calls_json,
    active_calls_count = EXCLUDED.active_calls_count,
    updated_at = EXCLUDED.updated_at
"""


async def upsert_decode_rate(
    pool: AsyncConnectionPool,
    *,
    instance_id: str,
    sys_num: int,
    sys_name: str,
    decoderate_raw: float,
    decoderate_pct: float,
    decoderate_interval_s: float | None,
    control_channel_hz: int | None,
    updated_at: datetime,
) -> None:
    """Insert or update the latest decode-rate snapshot for a system on an instance."""
    params = {
        "instance_id": instance_id,
        "sys_num": sys_num,
        "sys_name": sys_name,
        "decoderate_raw": decoderate_raw,
        "decoderate_pct": decoderate_pct,
        "decoderate_interval_s": decoderate_interval_s,
        "control_channel_hz": control_channel_hz,
        "updated_at": updated_at,
    }

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(SQL_UPSERT_DECODE_RATE, params)


async def upsert_recorders_snapshot(
    pool: AsyncConnectionPool,
    *,
    instance_id: str,
    recorders_json: dict,
    total_count: int,
    recording_count: int,
    idle_count: int,
    available_count: int,
    updated_at: datetime,
) -> None:
    """Insert or update the latest recorders snapshot for an instance."""
    params = {
        "instance_id": instance_id,
        "recorders_json": Json(recorders_json),
        "total_count": total_count,
        "recording_count": recording_count,
        "idle_count": idle_count,
        "available_count": available_count,
        "updated_at": updated_at,
    }

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(SQL_UPSERT_RECORDERS_SNAPSHOT, params)


async def upsert_calls_active_snapshot(
    pool: AsyncConnectionPool,
    *,
    instance_id: str,
    calls_json: dict,
    active_calls_count: int,
    updated_at: datetime,
) -> None:
    """Insert or update the latest active-calls snapshot for an instance."""
    params = {
        "instance_id": instance_id,
        "calls_json": Json(calls_json),
        "active_calls_count": active_calls_count,
        "updated_at": updated_at,
    }

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(SQL_UPSERT_CALLS_ACTIVE_SNAPSHOT, params)
