from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import KnowledgeSourceStatus
from app.schemas.common import TimestampedResponse


class KnowledgeBaseCreateRequest(BaseModel):
    monitor_profile_id: int
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)


class KnowledgeBaseUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None


class KnowledgeBaseResponse(TimestampedResponse):
    monitor_profile_id: int
    name: str
    description: str
    is_active: bool


class KnowledgeBaseListResponse(BaseModel):
    items: List[KnowledgeBaseResponse]
    total: int


class KnowledgeUrlSourceCreateRequest(BaseModel):
    monitor_profile_id: int
    knowledge_base_id: int
    url: str = Field(min_length=5, max_length=1000)
    title: str = Field(default="", max_length=255)


class KnowledgeSourceResponse(TimestampedResponse):
    monitor_profile_id: int
    knowledge_base_id: int
    source_type: str
    title: str
    uri_or_path: str
    status: KnowledgeSourceStatus
    error_message: str


class KnowledgeSourceListResponse(BaseModel):
    items: List[KnowledgeSourceResponse]
    total: int


class KnowledgeReindexRequest(BaseModel):
    monitor_profile_id: int
    knowledge_base_id: int


class KnowledgeSummaryResponse(BaseModel):
    monitor_profile_id: int
    knowledge_base_id: int
    knowledge_md: str
