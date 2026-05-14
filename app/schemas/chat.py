from typing import List
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedResponse


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    knowledge_base_id: Optional[int] = None


class Citation(BaseModel):
    timestamp: str
    quote: str


class ChatMessageResponse(TimestampedResponse):
    role: str
    content: str
    citations: List[Citation]
    confidence_score: float
    insufficient_evidence: bool


class ChatSessionResponse(TimestampedResponse):
    video_candidate_id: int
    created_by: str
