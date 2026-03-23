from typing import List

from pydantic import BaseModel, Field

from app.models.enums import IncidentStatus, RiskLevel
from app.schemas.common import TimestampedResponse


class IncidentCreateRequest(BaseModel):
    owner: str = Field(default="")
    notes: str = Field(default="")


class IncidentResponse(TimestampedResponse):
    video_candidate_id: int
    severity: RiskLevel
    status: IncidentStatus
    owner: str
    notes: str


class AlertResponse(TimestampedResponse):
    incident_id: int
    channel: str
    message: str
    is_sent: bool


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int

