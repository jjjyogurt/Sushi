from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import QueueState


class VideoCandidate(TimestampMixin, Base):
    __tablename__ = "video_candidates"
    __table_args__ = (
        Index("ix_video_candidates_title_fingerprint", "title_fingerprint"),
        Index("ix_video_candidates_queue_state", "queue_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_profile_id: Mapped[int] = mapped_column(ForeignKey("monitor_profiles.id"), nullable=False, index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    video_url: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_reason: Mapped[str] = mapped_column(Text, default="")
    queue_state: Mapped[QueueState] = mapped_column(Enum(QueueState), default=QueueState.DISCOVERED, nullable=False)

    monitor_profile = relationship("MonitorProfile")

