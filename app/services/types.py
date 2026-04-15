from dataclasses import dataclass
from datetime import datetime
from typing import List

from app.models.enums import RiskLevel, Sentiment


@dataclass(frozen=True)
class DiscoveredVideo:
    youtube_video_id: str
    video_url: str
    title: str
    channel_name: str
    language: str
    published_at: datetime
    description: str


@dataclass(frozen=True)
class TranscriptOutput:
    full_text: str
    segments: List[dict]
    source_language: str


@dataclass(frozen=True)
class AnalysisOutput:
    transcript_text: str
    summary_text: str
    translated_summary: str
    summary_headline: str
    summary_body: str
    business_impact: str
    sentiment: Sentiment
    risk_level: RiskLevel
    confidence_score: float
    evidence: List[dict]
    insights: List[str]
    praise_points: List[str]
    criticism_points: List[str]
    action_recommendation: str


@dataclass(frozen=True)
class CommentsAnalysisOutput:
    summary: str
    highlights: List[dict]
    lowlights: List[dict]


@dataclass(frozen=True)
class ChatOutput:
    content: str
    citations: List[dict]
    confidence_score: float
    insufficient_evidence: bool

