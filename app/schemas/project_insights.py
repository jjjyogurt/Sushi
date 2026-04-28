from typing import List, Optional

from pydantic import BaseModel

from app.schemas.common import TimestampedResponse


class ProjectInsightReportResponse(TimestampedResponse):
    monitor_profile_id: int
    analyzed_video_count: int
    total_video_count: int
    excluded_video_count: int
    coverage_pct: float
    overall_sentiment: str
    risk_level: str
    risk_score: float
    summary_headline: str
    summary_body: str
    business_impact: str
    praise_points: List[str]
    criticism_points: List[str]
    user_recommendations: List[str]
    excluded_reasons: List[str]
    report_markdown: str


class ProjectInsightHistoryResponse(BaseModel):
    items: List[ProjectInsightReportResponse]
    total: int


class ProjectInsightCurrentResponse(BaseModel):
    current: Optional[ProjectInsightReportResponse]
