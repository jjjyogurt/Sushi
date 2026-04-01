from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocRow(TimestampMixin, Base):
    __tablename__ = "voc_rows"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("voc_uploads.id"), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    cleaned_content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    error_message: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="")
    confidence: Mapped[float] = mapped_column(default=0.0)
    insight_id: Mapped[Optional[int]] = mapped_column(ForeignKey("voc_insights.id"), nullable=True, index=True)
