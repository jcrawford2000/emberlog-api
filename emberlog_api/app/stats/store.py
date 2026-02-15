"""In-memory stats store placeholders for future stories."""

from datetime import datetime, timezone
import logging

from emberlog_api.app.stats.models import StatsSourceStatusOut


log = logging.getLogger("emberlog_api.stats.store")
_source_status: StatsSourceStatusOut | None = None


def get_source_status() -> StatsSourceStatusOut | None:
    """Return the current ingest source status snapshot."""
    return _source_status


def mark_source_connected(source_id: str) -> None:
    """Mark a source as connected and refresh last_seen."""
    _set_source_status(source_id=source_id, connected=True)


def mark_source_seen(source_id: str) -> None:
    """Refresh source status after a valid message is received."""
    _set_source_status(source_id=source_id, connected=True)


def mark_source_disconnected(source_id: str) -> None:
    """Mark a source as disconnected while preserving source identity."""
    _set_source_status(source_id=source_id, connected=False)


def _set_source_status(source_id: str, connected: bool) -> None:
    global _source_status
    _source_status = StatsSourceStatusOut(
        source_id=source_id,
        connected=connected,
        last_seen=datetime.now(timezone.utc),
    )


def reset_source_status() -> None:
    """Reset in-memory source status (tests only)."""
    global _source_status
    _source_status = None
