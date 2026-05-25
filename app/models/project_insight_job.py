from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ProjectInsightJobStatus


class ProjectInsightJob(TimestampMixin, Base):
    __tablename__ = "project_insight_jobs"
    __table_args__ = (
        Index("ix_project_insight_jobs_profile_status_created", "monitor_profile_id", "status", "created_at"),
        Index("ix_project_insight_jobs_status_created", "status", "created_at"),
        Index(
            "ux_project_insight_jobs_one_active_per_profile",
            "monitor_profile_id",
            unique=True,
            sqlite_where=text("status IN ('QUEUED', 'RUNNING')"),
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_profile_id: Mapped[int] = mapped_column(ForeignKey("monitor_profiles.id"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False, default="system")
    status: Mapped[ProjectInsightJobStatus] = mapped_column(
        Enum(ProjectInsightJobStatus),
        nullable=False,
        default=ProjectInsightJobStatus.QUEUED,
    )
    report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("project_insight_reports.id"), nullable=True, index=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    monitor_profile = relationship("MonitorProfile")
    report = relationship("ProjectInsightReport")
