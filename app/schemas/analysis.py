from typing import List
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.schemas.common import TimestampedResponse


class AnalysisRequest(BaseModel):
    force_reanalyze: bool = False
    knowledge_base_id: Optional[int] = None


class EvidenceItem(BaseModel):
    timestamp: str
    quote: str
    reason: str


class AnalysisResponse(TimestampedResponse):
    video_candidate_id: int
    analysis_version: str
    model_name: str
    status: AnalysisStatus
    transcript_text: str
    summary_text: str
    translated_summary: str
    summary_headline: str = ""
    summary_body: str = ""
    business_impact: str = ""
    sentiment: Sentiment
    risk_level: RiskLevel
    confidence_score: float = Field(default=0.0)
    evidence: List[EvidenceItem]
    insights: List[str] = Field(default_factory=list)
    praise_points: List[str] = Field(default_factory=list)
    criticism_points: List[str] = Field(default_factory=list)
    action_recommendation: str = ""
    error_message: str

