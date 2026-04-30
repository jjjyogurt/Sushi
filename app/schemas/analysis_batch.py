from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.enums import AnalysisBatchItemStatus, AnalysisBatchStatus


class AnalysisBatchCreateRequest(BaseModel):
    monitor_profile_id: Optional[int] = None


class AnalysisBatchItemResponse(BaseModel):
    id: int
    batch_id: int
    video_id: int
    status: AnalysisBatchItemStatus
    attempt_count: int
    error_message: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AnalysisBatchResponse(BaseModel):
    id: int
    monitor_profile_id: Optional[int] = None
    created_by: str
    status: AnalysisBatchStatus
    total_count: int
    processed_count: int
    success_count: int
    failed_count: int
    last_error: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AnalysisBatchDetailResponse(BaseModel):
    batch: AnalysisBatchResponse
    items: List[AnalysisBatchItemResponse]
