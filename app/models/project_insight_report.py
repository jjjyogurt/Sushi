from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProjectInsightReport(TimestampMixin, Base):
    __tablename__ = "project_insight_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_profile_id: Mapped[int] = mapped_column(ForeignKey("monitor_profiles.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en", index=True)
    analyzed_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overall_sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary_headline: Mapped[str] = mapped_column(Text, default="")
    summary_body: Mapped[str] = mapped_column(Text, default="")
    praise_points_json: Mapped[str] = mapped_column(Text, default="[]")
    criticism_points_json: Mapped[str] = mapped_column(Text, default="[]")
    user_recommendations_json: Mapped[str] = mapped_column(Text, default="[]")
    excluded_reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    sentiment_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    risk_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    reach_metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    top_negative_videos_json: Mapped[str] = mapped_column(Text, default="[]")
    report_markdown: Mapped[str] = mapped_column(Text, default="")
