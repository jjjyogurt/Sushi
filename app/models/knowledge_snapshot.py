from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class KnowledgeSnapshot(TimestampMixin, Base):
    __tablename__ = "knowledge_snapshots"
    __table_args__ = (Index("ix_knowledge_snapshot_kb", "knowledge_base_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_profile_id: Mapped[int] = mapped_column(ForeignKey("monitor_profiles.id"), nullable=False, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    knowledge_md: Mapped[str] = mapped_column(Text, default="")
    source_set_hash: Mapped[str] = mapped_column(Text, default="")

    knowledge_base = relationship("KnowledgeBase")
