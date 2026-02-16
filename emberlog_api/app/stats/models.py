"""Pydantic models for stats feature routes."""

from pydantic import BaseModel, Field


class StatsSystemsOut(BaseModel):
    """Placeholder response payload for system stats."""

    source_status: dict[str, str] | None = None
    systems: list[dict[str, str]] = Field(default_factory=list)
    latest_decode: dict[str, str] = Field(default_factory=dict)

