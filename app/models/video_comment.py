from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class VideoComment(TimestampMixin, Base):
    __tablename__ = "video_comments"
    __table_args__ = (
        Index("ix_video_comments_video_candidate_id", "video_candidate_id"),
        Index("ix_video_comments_youtube_comment_id", "youtube_comment_id"),
        Index(
            "ix_video_comments_video_youtube_comment_id",
            "video_candidate_id",
            "youtube_comment_id",
            unique=True,
        ),
        Index("ix_video_comments_published_at", "published_at"),
        Index("ix_video_comments_parent_comment_id", "parent_comment_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    video_candidate_id: Mapped[int] = mapped_column(ForeignKey("video_candidates.id"), nullable=False)
    youtube_comment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_comment_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at_remote: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    video_candidate = relationship("VideoCandidate")
