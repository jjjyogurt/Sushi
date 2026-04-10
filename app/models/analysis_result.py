from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment


class AnalysisResult(TimestampMixin, Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index(
            "ix_analysis_video_version_language",
            "video_candidate_id",
            "analysis_version",
            "language",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    video_candidate_id: Mapped[int] = mapped_column(ForeignKey("video_candidates.id"), nullable=False, index=True)
    analysis_version: Mapped[str] = mapped_column(String(40), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    model_name: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(Enum(AnalysisStatus), default=AnalysisStatus.QUEUED, nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    summary_text: Mapped[str] = mapped_column(Text, default="")
    translated_summary: Mapped[str] = mapped_column(Text, default="")
    summary_headline: Mapped[str] = mapped_column(Text, default="")
    summary_body: Mapped[str] = mapped_column(Text, default="")
    business_impact: Mapped[str] = mapped_column(Text, default="")
    comment_summary_text: Mapped[str] = mapped_column(Text, default="")
    comment_highlights_json: Mapped[str] = mapped_column(Text, default="[]")
    comment_lowlights_json: Mapped[str] = mapped_column(Text, default="[]")
    sentiment: Mapped[Sentiment] = mapped_column(Enum(Sentiment), default=Sentiment.NEUTRAL, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.LOW, nullable=False)
    confidence_score: Mapped[str] = mapped_column(String(16), default="0.0")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    insights_json: Mapped[str] = mapped_column(Text, default="[]")
    error_message: Mapped[str] = mapped_column(Text, default="")

    video_candidate = relationship("VideoCandidate")

