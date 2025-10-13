import logging
from typing import Any

from psycopg.types.json import Json

from emberlog_api.models.incident import IncidentIn, IncidentOut, NewIncident

SQL_INSERT = """
INSERT INTO incidents (dispatched_at, special_call, units, channel, incident_type, address, source_audio, original_text, transcript, parsed)
VALUES (%(dispatched_at)s, %(special_call)s, %(units)s, %(channel)s, %(incident_type)s, %(address)s, %(source_audio)s, %(original_text)s, %(transcript)s, %(parsed)s)
RETURNING id, created_at
"""

SQL_OUTBOX_INSERT = """
INSERT INTO incident_outbox (incident_id, event_type, created_at, payload)
VALUES (%(incident_id)s, %(event_type)s, %(created_at)s, %(payload)s)
RETURNING id
"""

SQL_SELECT_INCIDENT = """
SELECT id, dispatched_at, special_call, units, channel, incident_type, address, source_audio, original_text, transcript, parsed, created_at
FROM incidents
WHERE id=%(id)s
"""

log = logging.getLogger("emberlog_api.v1.db.repositories.incidents")


async def insert_incident(pool, payload: IncidentIn) -> dict[str, Any]:
    log.debug("Inserting new incident")
    params = {
        "dispatched_at": payload.dispatched_at,
        "special_call": payload.special_call,
        "units": payload.units,
        "channel": payload.channel,
        "incident_type": payload.incident_type,
        "address": payload.address,
        "source_audio": payload.source_audio,
        "original_text": payload.original_text,
        "transcript": payload.transcript,
        "parsed": Json(payload.parsed),
    }
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(SQL_INSERT, params)
            row = await cur.fetchone()
            inc_id = row[0]
            created_at = row[1]
            log.info("Incident %s inserted at %s", inc_id, created_at)
            outbox_params = {
                "incident_id": inc_id,
                "created_at": created_at,
                "payload": payload.model_dump_json(),
                "event_type": "incident.created",
            }
            log.info("Adding to notifier outbox")
            await cur.execute(SQL_OUTBOX_INSERT, outbox_params)
            row = await cur.fetchone()
            log.info("Notifier Outbox record created. ID:%s", row[0])
            return {"id": inc_id, "created_at": created_at}


async def select_incident(pool, incident_id: int) -> IncidentOut:
    params = {
        "id": incident_id,
    }
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(SQL_SELECT_INCIDENT, params)
            row = await cur.fetchone()
            if row is None:
                raise ValueError(f"Incident {incident_id} not found")
            return IncidentOut(
                id=row[0],
                dispatched_at=row[1],
                special_call=row[2],
                units=row[3],
                channel=row[4],
                incident_type=row[5],
                address=row[6],
                source_audio=row[7],
                original_text=row[8],
                transcript=row[9],
                parsed=row[10],
                created_at=row[11],
            )
