"""Pydantic models for stats feature routes."""

from datetime import datetime

from pydantic import BaseModel, Field


class StatsSourceStatusOut(BaseModel):
    """Current ingest source connection status."""

    source_id: str
    connected: bool
    last_seen: datetime


class StatsSystemsOut(BaseModel):
    """Response payload for system stats."""

    source_status: StatsSourceStatusOut | None = None
    systems: list[dict[str, str]] = Field(default_factory=list)
    latest_decode: dict[str, str] = Field(default_factory=dict)
