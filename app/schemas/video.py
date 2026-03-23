from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import QueueState, Sentiment
from app.schemas.common import TimestampedResponse


class VideoDiscoveryRequest(BaseModel):
    monitor_profile_id: int
    max_results: int = Field(default=20, ge=1, le=100)


class ManualVideoCreateRequest(BaseModel):
    monitor_profile_id: int
    video_url: str = Field(min_length=10, max_length=255)
    language: Optional[str] = Field(default=None, max_length=20)


class VideoApproveRequest(BaseModel):
    approved: bool


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


class VideoListResponse(BaseModel):
    items: List[VideoResponse]
    total: int
    title_filter: Optional[str] = None


class VideoBulkAddResponse(BaseModel):
    items: List[VideoResponse]
    total: int

