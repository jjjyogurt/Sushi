from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocInsight(TimestampMixin, Base):
    __tablename__ = "voc_insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("voc_uploads.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), default="")
    category: Mapped[str] = mapped_column(String(40), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(default=0.0)
    severity: Mapped[str] = mapped_column(String(40), default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    team: Mapped[str] = mapped_column(String(120), default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[str] = mapped_column(String(40), default="")
