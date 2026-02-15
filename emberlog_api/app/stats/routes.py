"""HTTP routes for stats feature scaffolding."""

import logging

from fastapi import APIRouter, Depends

from emberlog_api.app.stats.auth import require_stats_api_key
from emberlog_api.app.stats.models import StatsSystemsOut
from emberlog_api.app.stats.service import get_systems_snapshot


log = logging.getLogger("emberlog_api.stats.routes")
router = APIRouter(
    prefix="/stats", tags=["stats"], dependencies=[Depends(require_stats_api_key)]
)


@router.get("/systems", response_model=StatsSystemsOut, name="get_stats_systems")
async def get_stats_systems() -> StatsSystemsOut:
    """Story 1 placeholder endpoint for stats systems snapshot."""
    return get_systems_snapshot()
