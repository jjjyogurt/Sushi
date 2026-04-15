from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VideoWatchlistEntry(TimestampMixin, Base):
    __tablename__ = "video_watchlist_entries"
    __table_args__ = (
        UniqueConstraint("video_candidate_id", "user_id", name="uq_watchlist_video_user"),
        Index("ix_watchlist_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    video_candidate_id: Mapped[int] = mapped_column(ForeignKey("video_candidates.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
