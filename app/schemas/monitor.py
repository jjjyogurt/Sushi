from typing import List

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedResponse


class MonitorProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_keywords: List[str] = Field(min_length=1)
    markets: List[str] = Field(min_length=1)
    languages: List[str] = Field(min_length=1)
    key_products: List[str] = Field(default_factory=list)
    alert_sensitivity: str = Field(default="medium")
    proactive_monitoring_enabled: bool = False
    proactive_monitoring_cadence: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")


class MonitorProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_keywords: List[str] = Field(min_length=1)
    markets: List[str] = Field(min_length=1)
    languages: List[str] = Field(min_length=1)
    key_products: List[str] = Field(default_factory=list)
    alert_sensitivity: str = Field(default="medium")
    proactive_monitoring_enabled: bool = False
    proactive_monitoring_cadence: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")


class MonitorProfileMonitoringUpdate(BaseModel):
    proactive_monitoring_enabled: bool
    proactive_monitoring_cadence: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")


class MonitorProfileResponse(TimestampedResponse):
    name: str
    brand_keywords: List[str]
    markets: List[str]
    languages: List[str]
    key_products: List[str]
    alert_sensitivity: str
    is_active: bool
    proactive_monitoring_enabled: bool
    proactive_monitoring_cadence: str
    unseen_monitoring_update_count: int
    last_monitoring_digest: str
