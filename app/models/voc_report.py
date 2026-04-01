from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocReport(TimestampMixin, Base):
    __tablename__ = "voc_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("voc_projects.id"), nullable=False, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("voc_uploads.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    content: Mapped[str] = mapped_column(Text, default="")
    publish_block_reason: Mapped[str] = mapped_column(Text, default="")
    cleaner_skill_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voc_skill_versions.id"), nullable=True, index=True
    )
    analyzer_skill_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voc_skill_versions.id"), nullable=True, index=True
    )
    report_template_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voc_template_versions.id"), nullable=True, index=True
    )
