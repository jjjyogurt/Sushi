from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AnalysisStatus, QueueState, Sentiment
from app.schemas.common import TimestampedResponse

DISCOVERY_PUBLISH_WINDOW_MAX_DAYS = 366


class VideoDiscoveryRequest(BaseModel):
    monitor_profile_id: int
    max_results: int = Field(default=20, ge=1, le=100)
    published_after: Optional[datetime] = Field(
        default=None,
        description="Include videos with published_at >= this instant (UTC).",
    )
    published_before: Optional[datetime] = Field(
        default=None,
        description="Include videos with published_at < this instant (UTC).",
    )

    @staticmethod
    def _to_utc_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_publish_window(self):
        after = self.published_after
        before = self.published_before
        if after is not None:
            object.__setattr__(self, "published_after", self._to_utc_aware(after))
        if before is not None:
            object.__setattr__(self, "published_before", self._to_utc_aware(before))
        after = self.published_after
        before = self.published_before
        if after is not None and before is not None:
            if after >= before:
                raise ValueError("published_after must be earlier than published_before.")
            span = before - after
            if span > timedelta(days=DISCOVERY_PUBLISH_WINDOW_MAX_DAYS):
                raise ValueError(
                    f"Publish window must not exceed {DISCOVERY_PUBLISH_WINDOW_MAX_DAYS} days.",
                )
        return self


class ManualVideoCreateRequest(BaseModel):
    monitor_profile_id: int
    video_url: str = Field(min_length=10, max_length=255)
    language: Optional[str] = Field(default=None, max_length=20)


class VideoApproveRequest(BaseModel):
    approved: bool


class VideoAssigneeUpdateRequest(BaseModel):
    assigned_user_id: Optional[str] = Field(default=None, max_length=80)


class VideoSearchRequest(BaseModel):
    monitor_profile_id: int
    query: str = Field(min_length=2, max_length=160)
    max_results: int = Field(default=20, ge=1, le=100)


class VideoSearchCandidate(BaseModel):
    youtube_video_id: str
    video_url: str
    title: str
    channel_name: str
    language: str
    published_at: datetime
    description: str
    relevance_score: float
    relevance_reason: str
    can_add: bool
    block_reason: Optional[str] = None


class VideoSearchResponse(BaseModel):
    items: List[VideoSearchCandidate]
    total: int
    query: str


class VideoBulkAddCandidate(BaseModel):
    youtube_video_id: str = Field(min_length=3, max_length=64)
    video_url: str = Field(min_length=10, max_length=255)
    title: str = Field(min_length=2, max_length=255)
    channel_name: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=2, max_length=20)
    published_at: datetime
    description: str = Field(min_length=1)


class VideoBulkAddRequest(BaseModel):
    monitor_profile_id: int
    candidates: List[VideoBulkAddCandidate] = Field(min_length=1, max_length=50)


class VideoResponse(TimestampedResponse):
    monitor_profile_id: int
    monitor_profile_name: Optional[str] = None
    youtube_video_id: str
    video_url: str
    title: str
    channel_name: str
    language: str
    published_at: datetime
    relevance_score: float
    relevance_reason: str
    queue_state: QueueState
    sentiment_label: Optional[Sentiment] = None
    latest_analysis_status: Optional[AnalysisStatus] = None
    is_bookmarked: bool = False
    assigned_user_id: Optional[str] = None
    discovery_source: str = "manual"
    is_proactive_new: bool = False


class VideoReachResponse(BaseModel):
    video_id: int
    youtube_video_id: str
    view_count: Optional[int] = None
    subscriber_count: Optional[int] = None
    is_reach_available: bool = False


class VideoListResponse(BaseModel):
    items: List[VideoResponse]
    total: int
    risk_level: Optional[str] = None
    sentiment: Optional[str] = None


class VideoBulkAddResponse(BaseModel):
    items: List[VideoResponse]
    total: int
