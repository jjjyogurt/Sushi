from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.common import TimestampedResponse


class ProjectInsightReportResponse(TimestampedResponse):
    monitor_profile_id: int
    language: str = "en"
    analyzed_video_count: int
    total_video_count: int
    excluded_video_count: int
    coverage_pct: float
    overall_sentiment: str
    risk_level: str
    risk_score: float
    summary_headline: str
    summary_body: str
    top_risk_trigger: str = ""
    praise_points: List[str]
    criticism_points: List[str]
    user_recommendations: List[str]
    excluded_reasons: List[str]
    sentiment_breakdown: dict
    risk_breakdown: dict
    reach_metrics: dict
    top_negative_videos: List[dict]
    report_markdown: str


class ProjectInsightHistoryResponse(BaseModel):
    items: List[ProjectInsightReportResponse]
    total: int


class ProjectInsightCurrentResponse(BaseModel):
    current: Optional[ProjectInsightReportResponse]


class ProjectInsightJobResponse(TimestampedResponse):
    monitor_profile_id: int
    language: str = "en"
    created_by: str
    status: str
    report_id: Optional[int] = None
    last_error: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ProjectInsightActiveJobResponse(BaseModel):
    active: Optional[ProjectInsightJobResponse]
