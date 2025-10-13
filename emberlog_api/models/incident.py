from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class IncidentIn(BaseModel):
    dispatched_at: datetime
    special_call: bool = False
    units: Optional[List[str]]
    channel: Optional[str]
    incident_type: Optional[str]
    address: Optional[str]
    source_audio: str
    original_text: Optional[str] = None
    transcript: Optional[str]
    parsed: Optional[dict] = None


class LinkTarget(BaseModel):
    url: str = Field(alias="_url")
    model_config = ConfigDict(populate_by_name=True)


class Links(BaseModel):
    self: LinkTarget


class NewIncident(BaseModel):
    id: int
    created_at: datetime
    links: Links


class IncidentOut(BaseModel):
    id: int
    dispatched_at: datetime
    special_call: bool = False
    units: Optional[List[str]]
    channel: Optional[str]
    incident_type: Optional[str]
    address: Optional[str]
    source_audio: str
    original_text: Optional[str] = None
    transcript: Optional[str]
    parsed: Optional[dict] = None
    created_at: datetime
