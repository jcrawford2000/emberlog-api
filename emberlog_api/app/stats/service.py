"""Stats service layer placeholders and facade helpers."""

from emberlog_api.app.stats.models import StatsSystemsOut


def get_systems_snapshot() -> StatsSystemsOut:
    """Return the Story 1 placeholder systems payload."""
    return StatsSystemsOut(source_status=None, systems=[], latest_decode={})
