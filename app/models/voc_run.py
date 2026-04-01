from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocRun(TimestampMixin, Base):
    __tablename__ = "voc_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("voc_uploads.id"), nullable=False, index=True)
    run_type: Mapped[str] = mapped_column(String(40), default="cleaning")
    status: Mapped[str] = mapped_column(String(40), default="queued")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    cleaner_skill_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voc_skill_versions.id"), nullable=True, index=True
    )
    analyzer_skill_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voc_skill_versions.id"), nullable=True, index=True
    )
    report_template_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voc_template_versions.id"), nullable=True, index=True
    )
