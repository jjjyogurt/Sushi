from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AnalysisBatchItemStatus, AnalysisBatchStatus


class AnalysisBatch(TimestampMixin, Base):
    __tablename__ = "analysis_batches"
    __table_args__ = (
        Index("ix_analysis_batches_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("monitor_profiles.id"), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False, default="system")
    status: Mapped[AnalysisBatchStatus] = mapped_column(Enum(AnalysisBatchStatus), nullable=False, default=AnalysisBatchStatus.QUEUED)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    monitor_profile = relationship("MonitorProfile")
    items = relationship("AnalysisBatchItem", cascade="all, delete-orphan", back_populates="batch")


class AnalysisBatchItem(TimestampMixin, Base):
    __tablename__ = "analysis_batch_items"
    __table_args__ = (
        Index("ix_analysis_batch_items_batch_status", "batch_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("analysis_batches.id"), nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video_candidates.id"), nullable=False, index=True)
    status: Mapped[AnalysisBatchItemStatus] = mapped_column(Enum(AnalysisBatchItemStatus), nullable=False, default=AnalysisBatchItemStatus.QUEUED)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    batch = relationship("AnalysisBatch", back_populates="items")
    video = relationship("VideoCandidate")
