"""Stats service layer placeholders and facade helpers."""

from emberlog_api.app.stats.models import StatsSystemsOut
from emberlog_api.app.stats.store import get_source_status


def get_systems_snapshot() -> StatsSystemsOut:
    """Return the current systems payload with minimal source status."""
    return StatsSystemsOut(
        source_status=get_source_status(),
        systems=[],
        latest_decode={},
    )
