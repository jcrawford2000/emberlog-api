import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.api.v1.routers.sse import publish_incident
from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.db.repositories import incidents
from emberlog_api.models.incident import (
    IncidentIn,
    IncidentListOut,
    IncidentOut,
    Links,
    LinkTarget,
    NewIncident,
)
from emberlog_api.utils.loggersetup import configure_logging

configure_logging()
log = logging.getLogger("emberlog_api.v1.routers.incidents")

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/", name="list_incidents", response_model=IncidentListOut)
async def list_incidents(
    *,
    from_dispatched_at: datetime | None = Query(None),
    to_dispatched_at: datetime | None = Query(None),
    incident_type: str | None = Query(None),
    channel: str | None = Query(None),
    units: list[str] | None = Query(None),
    address_search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    pool: AsyncConnectionPool = Depends(get_pool),
):
    limit = page_size
    offset = (page - 1) * page_size
    items, total = await incidents.list_incidents(
        pool=pool,
        from_dispatched_at=from_dispatched_at,
        to_dispatched_at=to_dispatched_at,
        incident_type=incident_type,
        channel=channel,
        units=units,
        address_search=address_search,
        limit=limit,
        offset=offset,
    )

    return IncidentListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{incident_id}", name="get_incident", response_model=IncidentOut)
async def get_incident(incident_id: int, pool: AsyncConnectionPool = Depends(get_pool)):
    resp = await incidents.select_incident(pool=pool, incident_id=incident_id)
    return resp


@router.post(
    "/",
    response_model=NewIncident,
    status_code=status.HTTP_201_CREATED,
    name="create_incident",
)
async def create_incident(
    request: Request, payload: IncidentIn, pool: AsyncConnectionPool = Depends(get_pool)
):
    resp = await incidents.insert_incident(pool=pool, payload=payload)
    resp_id = resp["id"]
    resp_created_at = resp["created_at"]
    location = request.url_for("get_incident", incident_id=resp_id)
    log.debug(f"Inserted incident with id {resp_id}: {location}")
    links = Links(self=LinkTarget(_url=str(location)))
    new_incident = NewIncident(id=resp_id, created_at=resp_created_at, links=links)
    incident = IncidentOut(
        id=new_incident.id,
        dispatched_at=payload.dispatched_at,
        special_call=payload.special_call,
        units=payload.units,
        channel=payload.channel,
        incident_type=payload.incident_type,
        address=payload.address,
        source_audio=payload.source_audio,
        original_text=payload.original_text,
        transcript=payload.transcript,
        parsed=payload.parsed,
        created_at=new_incident.created_at,
    )
    await publish_incident(incident)

    log.debug("Published to SSE")
    return NewIncident(id=resp_id, created_at=resp_created_at, links=links)
