from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedResponse


class VocProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="")


class VocProjectUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="")
    status: str = Field(default="draft")


class VocProjectResponse(TimestampedResponse):
    name: str
    description: str
    status: str
    is_active: bool


class VocUploadResponse(TimestampedResponse):
    project_id: int
    source_type: str
    filename: str
    status: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    error_message: str


class VocRowResponse(TimestampedResponse):
    upload_id: int
    row_index: int
    raw_content: str
    cleaned_content: str
    status: str
    error_message: str
    category: str
    confidence: float
    insight_id: Optional[int]


class VocRunCreate(BaseModel):
    upload_id: int


class VocRunResponse(TimestampedResponse):
    upload_id: int
    run_type: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_rows: int
    processed_rows: int
    failed_rows: int
    error_message: str
    cleaner_skill_version_id: Optional[int]
    analyzer_skill_version_id: Optional[int]
    report_template_version_id: Optional[int]


class VocInsightResponse(TimestampedResponse):
    upload_id: int
    title: str
    category: str
    summary: str
    confidence: float
    severity: str
    owner: str
    team: str
    recommended_action: str
    due_date: str


class VocEvidenceResponse(TimestampedResponse):
    insight_id: int
    row_id: int
    evidence_type: str
    snippet: str


class VocReportUpdate(BaseModel):
    content: str = Field(min_length=1)


class VocReportResponse(TimestampedResponse):
    project_id: int
    upload_id: int
    status: str
    content: str
    publish_block_reason: str
    cleaner_skill_version_id: Optional[int]
    analyzer_skill_version_id: Optional[int]
    report_template_version_id: Optional[int]


class VocPublishResponse(BaseModel):
    allowed: bool
    requires_acknowledgment: bool
    reason: str


class VocSkillVersionCreate(BaseModel):
    skill_type: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1)


class VocSkillVersionUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1)


class VocSkillVersionResponse(TimestampedResponse):
    skill_type: str
    name: str
    content: str
    status: str
    is_active: bool


class VocTemplateVersionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1)


class VocTemplateVersionUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1)


class VocTemplateVersionResponse(TimestampedResponse):
    name: str
    content: str
    status: str
    is_active: bool


class VocListResponse(BaseModel):
    items: List
    total: int


class VocSkillDefaultsResponse(BaseModel):
    cleaner: str
    analyzer: str
