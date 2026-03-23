from typing import List

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedResponse


class MonitorProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_keywords: List[str] = Field(min_length=1)
    markets: List[str] = Field(min_length=1)
    languages: List[str] = Field(min_length=1)
    alert_sensitivity: str = Field(default="medium")


class MonitorProfileResponse(TimestampedResponse):
    name: str
    brand_keywords: List[str]
    markets: List[str]
    languages: List[str]
    alert_sensitivity: str
    is_active: bool

