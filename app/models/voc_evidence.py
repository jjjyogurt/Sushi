from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocEvidence(TimestampMixin, Base):
    __tablename__ = "voc_evidence"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    insight_id: Mapped[int] = mapped_column(ForeignKey("voc_insights.id"), nullable=False, index=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("voc_rows.id"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(40), default="supporting")
    snippet: Mapped[str] = mapped_column(Text, default="")
