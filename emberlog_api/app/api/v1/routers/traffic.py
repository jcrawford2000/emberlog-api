import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.db.repositories import traffic as traffic_repo

log = logging.getLogger("emberlog_api.v1.routers.traffic")

router = APIRouter(prefix="/traffic", tags=["traffic"])


class TrafficDecodeSiteOut(BaseModel):
    group: str
    sys_num: int
    sys_name: str
    decode_rate_pct: float
    control_channel_mhz: float | None
    interval_s: float | None
    updated_at: str | None
    status: str


class TrafficSummaryOut(BaseModel):
    instance_id: str
    last_seen_at: str | None
    active_calls_count: int
    recorders_total: int
    recorders_recording: int
    recorders_idle: int
    recorders_available: int
    recorders_updated_at: str | None
    decode_sites: list[TrafficDecodeSiteOut]


class TrafficLiveCallOut(BaseModel):
    id: str
    started_at: str | None
    elapsed_s: int
    sys_num: int | None
    sys_name: str
    group: str
    talkgroup_id: int | None
    talkgroup: str | None
    description: str | None
    category: str | None
    tag: str | None
    freq_mhz: float | None
    encrypted: bool
    emergency: bool
    phase2_tdma: bool
    tdma_slot: int | None
    unit: int | None
    src_num: int | None
    rec_num: int | None
    recorder_id: str | None


class TrafficLiveCallsOut(BaseModel):
    instance_id: str
    updated_at: str | None
    calls: list[TrafficLiveCallOut]


def _to_iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _group_from_sys_name(sys_name: str) -> str:
    return sys_name.split("-", 1)[0] if sys_name else ""


def _decode_status(decode_rate_pct: float) -> str:
    if decode_rate_pct >= 90.0:
        return "ok"
    if decode_rate_pct >= 70.0:
        return "warn"
    return "bad"


def _parse_sys_name_filter(values: list[str] | None) -> set[str] | None:
    if not values:
        return None

    normalized: set[str] = set()
    for value in values:
        for item in value.split(","):
            stripped = item.strip()
            if stripped:
                normalized.add(stripped)

    return normalized or None


@router.get("/summary", response_model=TrafficSummaryOut)
async def get_traffic_summary(
    *,
    instance_id: str = Query("trunk-recorder"),
    pool: AsyncConnectionPool = Depends(get_pool),
) -> TrafficSummaryOut:
    try:
        decode_rows = await traffic_repo.list_decode_rate_latest(
            pool=pool,
            instance_id=instance_id,
        )
        recorders_row = await traffic_repo.select_recorders_snapshot_latest(
            pool=pool,
            instance_id=instance_id,
        )
        calls_row = await traffic_repo.select_calls_active_snapshot_latest(
            pool=pool,
            instance_id=instance_id,
        )
    except Exception:
        log.exception(
            "failed to read traffic summary data",
            extra={"instance_id": instance_id, "endpoint": "traffic.summary"},
        )
        raise

    log.debug(
        "traffic summary source snapshot",
        extra={
            "instance_id": instance_id,
            "decode_rows_count": len(decode_rows),
            "has_recorders_snapshot": recorders_row is not None,
            "has_calls_snapshot": calls_row is not None,
        },
    )

    decode_sites: list[TrafficDecodeSiteOut] = []
    seen_times: list[datetime] = []

    for row in decode_rows:
        updated_at = row.get("updated_at")
        if isinstance(updated_at, datetime):
            seen_times.append(updated_at)

        sys_name = str(row["sys_name"])
        decode_rate_pct = float(row["decoderate_pct"])
        control_channel_hz = row.get("control_channel_hz")
        decode_sites.append(
            TrafficDecodeSiteOut(
                group=_group_from_sys_name(sys_name),
                sys_num=int(row["sys_num"]),
                sys_name=sys_name,
                decode_rate_pct=decode_rate_pct,
                control_channel_mhz=(
                    float(control_channel_hz) / 1_000_000.0
                    if control_channel_hz is not None
                    else None
                ),
                interval_s=(
                    float(row["decoderate_interval_s"])
                    if row.get("decoderate_interval_s") is not None
                    else None
                ),
                updated_at=_to_iso_z(updated_at)
                if isinstance(updated_at, datetime)
                else None,
                status=_decode_status(decode_rate_pct),
            )
        )

    decode_sites.sort(key=lambda item: (item.group, item.sys_name))

    active_calls_count = 0
    calls_updated_at: datetime | None = None
    if calls_row:
        active_calls_count = int(calls_row["active_calls_count"])
        calls_updated_value = calls_row.get("updated_at")
        if isinstance(calls_updated_value, datetime):
            calls_updated_at = calls_updated_value
            seen_times.append(calls_updated_at)

    recorders_total = 0
    recorders_recording = 0
    recorders_idle = 0
    recorders_available = 0
    recorders_updated_at: datetime | None = None

    if recorders_row:
        recorders_total = int(recorders_row["total_count"])
        recorders_recording = int(recorders_row["recording_count"])
        recorders_idle = int(recorders_row["idle_count"])
        recorders_available = int(recorders_row["available_count"])
        recorders_updated_value = recorders_row.get("updated_at")
        if isinstance(recorders_updated_value, datetime):
            recorders_updated_at = recorders_updated_value
            seen_times.append(recorders_updated_at)

    last_seen_at = max(seen_times) if seen_times else None

    response = TrafficSummaryOut(
        instance_id=instance_id,
        last_seen_at=_to_iso_z(last_seen_at),
        active_calls_count=active_calls_count,
        recorders_total=recorders_total,
        recorders_recording=recorders_recording,
        recorders_idle=recorders_idle,
        recorders_available=recorders_available,
        recorders_updated_at=_to_iso_z(recorders_updated_at),
        decode_sites=decode_sites,
    )
    log.info(
        "traffic summary served",
        extra={
            "instance_id": instance_id,
            "decode_sites_count": len(response.decode_sites),
            "active_calls_count": response.active_calls_count,
            "recorders_total": response.recorders_total,
            "last_seen_at": response.last_seen_at,
        },
    )
    return response


@router.get("/live-calls", response_model=TrafficLiveCallsOut)
async def get_traffic_live_calls(
    *,
    instance_id: str = Query("trunk-recorder"),
    sys_name: list[str] | None = Query(
        None,
        description="Optional sys_name filters; supports repeated params and comma-separated values.",
    ),
    q: str | None = Query(None),
    hide_encrypted: bool = Query(False),
    pool: AsyncConnectionPool = Depends(get_pool),
) -> TrafficLiveCallsOut:
    q_present = bool(q)
    try:
        snapshot_row = await traffic_repo.select_calls_active_snapshot_latest(
            pool=pool,
            instance_id=instance_id,
        )
    except Exception:
        log.exception(
            "failed to read live calls snapshot",
            extra={"instance_id": instance_id, "endpoint": "traffic.live_calls"},
        )
        raise

    if snapshot_row is None:
        log.info(
            "traffic live-calls served",
            extra={
                "instance_id": instance_id,
                "returned_calls_count": 0,
                "hide_encrypted": hide_encrypted,
                "q_present": q_present,
                "sys_name_filter_count": 0,
            },
        )
        return TrafficLiveCallsOut(instance_id=instance_id, updated_at=None, calls=[])

    updated_at = snapshot_row.get("updated_at")
    calls_json = snapshot_row.get("calls_json")
    if not isinstance(calls_json, dict):
        log.error(
            "live calls snapshot payload is malformed",
            extra={
                "instance_id": instance_id,
                "endpoint": "traffic.live_calls",
                "reason": "calls_json_not_object",
            },
        )
        return TrafficLiveCallsOut(
            instance_id=instance_id,
            updated_at=_to_iso_z(updated_at) if isinstance(updated_at, datetime) else None,
            calls=[],
        )

    calls = calls_json.get("calls")
    if not isinstance(calls, list):
        log.error(
            "live calls snapshot payload is malformed",
            extra={
                "instance_id": instance_id,
                "endpoint": "traffic.live_calls",
                "reason": "calls_not_list",
            },
        )
        return TrafficLiveCallsOut(
            instance_id=instance_id,
            updated_at=_to_iso_z(updated_at) if isinstance(updated_at, datetime) else None,
            calls=[],
        )

    sys_name_filter = _parse_sys_name_filter(sys_name)
    log.debug(
        "parsed live-calls filters",
        extra={
            "instance_id": instance_id,
            "sys_name_filters": sorted(sys_name_filter) if sys_name_filter else [],
            "sys_name_filter_count": len(sys_name_filter) if sys_name_filter else 0,
            "q_present": q_present,
            "hide_encrypted": hide_encrypted,
        },
    )
    q_lower = q.lower() if q else None

    input_calls_count = len(calls)
    after_sys_name_count = 0
    after_q_count = 0
    after_hide_encrypted_count = 0
    normalized_calls: list[tuple[float | None, int, TrafficLiveCallOut]] = []
    for call in calls:
        if not isinstance(call, dict):
            continue

        call_sys_name = str(call.get("sys_name") or "")

        if sys_name_filter and call_sys_name not in sys_name_filter:
            continue
        after_sys_name_count += 1

        encrypted = bool(call.get("encrypted", False))
        if hide_encrypted and encrypted:
            continue
        after_hide_encrypted_count += 1

        alpha_tag = str(call.get("talkgroup_alpha_tag") or "")
        description = str(call.get("talkgroup_description") or "")
        if q_lower and q_lower not in alpha_tag.lower() and q_lower not in description.lower():
            continue
        after_q_count += 1

        start_epoch_raw = call.get("start_time")
        started_at_dt: datetime | None = None
        started_at_epoch: float | None = None
        if start_epoch_raw is not None:
            try:
                started_at_epoch = float(start_epoch_raw)
                started_at_dt = datetime.fromtimestamp(started_at_epoch, tz=UTC)
            except (TypeError, ValueError, OSError):
                started_at_epoch = None
                started_at_dt = None

        elapsed_raw = call.get("elapsed")
        try:
            elapsed_s = int(elapsed_raw) if elapsed_raw is not None else 0
        except (TypeError, ValueError):
            elapsed_s = 0

        src_num_raw = call.get("src_num")
        rec_num_raw = call.get("rec_num")
        try:
            src_num = int(src_num_raw) if src_num_raw is not None else None
        except (TypeError, ValueError):
            src_num = None
        try:
            rec_num = int(rec_num_raw) if rec_num_raw is not None else None
        except (TypeError, ValueError):
            rec_num = None

        freq_raw = call.get("freq")
        try:
            freq_mhz = float(freq_raw) / 1_000_000.0 if freq_raw is not None else None
        except (TypeError, ValueError):
            freq_mhz = None

        try:
            sys_num = int(call["sys_num"]) if call.get("sys_num") is not None else None
        except (TypeError, ValueError):
            sys_num = None

        talkgroup_raw = call.get("talkgroup")
        try:
            talkgroup_id = int(talkgroup_raw) if talkgroup_raw is not None else None
        except (TypeError, ValueError):
            talkgroup_id = None

        unit_raw = call.get("unit")
        try:
            unit = int(unit_raw) if unit_raw is not None else None
        except (TypeError, ValueError):
            unit = None

        tdma_slot_raw = call.get("tdma_slot")
        try:
            tdma_slot = int(tdma_slot_raw) if tdma_slot_raw is not None else None
        except (TypeError, ValueError):
            tdma_slot = None

        normalized = TrafficLiveCallOut(
            id=str(call.get("id") or ""),
            started_at=_to_iso_z(started_at_dt),
            elapsed_s=elapsed_s,
            sys_num=sys_num,
            sys_name=call_sys_name,
            group=_group_from_sys_name(call_sys_name),
            talkgroup_id=talkgroup_id,
            talkgroup=(str(call.get("talkgroup_alpha_tag")) if call.get("talkgroup_alpha_tag") is not None else None),
            description=(str(call.get("talkgroup_description")) if call.get("talkgroup_description") is not None else None),
            category=(str(call.get("talkgroup_group")) if call.get("talkgroup_group") is not None else None),
            tag=(str(call.get("talkgroup_tag")) if call.get("talkgroup_tag") is not None else None),
            freq_mhz=freq_mhz,
            encrypted=encrypted,
            emergency=bool(call.get("emergency", False)),
            phase2_tdma=bool(call.get("phase2_tdma", False)),
            tdma_slot=tdma_slot,
            unit=unit,
            src_num=src_num,
            rec_num=rec_num,
            recorder_id=(f"{src_num}_{rec_num}" if src_num is not None and rec_num is not None else None),
        )
        normalized_calls.append((started_at_epoch, elapsed_s, normalized))

    normalized_calls.sort(
        key=lambda item: (
            item[0] is not None,
            item[0] if item[0] is not None else float(item[1]),
        ),
        reverse=True,
    )

    log.debug(
        "live-calls filtering complete",
        extra={
            "instance_id": instance_id,
            "input_calls_count": input_calls_count,
            "after_sys_name_count": after_sys_name_count,
            "after_q_count": after_q_count,
            "after_hide_encrypted_count": after_hide_encrypted_count,
            "returned_calls_count": len(normalized_calls),
            "sort_mode": "started_at_desc_else_elapsed_desc",
        },
    )
    response = TrafficLiveCallsOut(
        instance_id=instance_id,
        updated_at=_to_iso_z(updated_at) if isinstance(updated_at, datetime) else None,
        calls=[item[2] for item in normalized_calls],
    )
    log.info(
        "traffic live-calls served",
        extra={
            "instance_id": instance_id,
            "returned_calls_count": len(response.calls),
            "hide_encrypted": hide_encrypted,
            "q_present": q_present,
            "sys_name_filter_count": len(sys_name_filter) if sys_name_filter else 0,
        },
    )
    return response
