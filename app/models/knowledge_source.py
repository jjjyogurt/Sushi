from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import KnowledgeSourceStatus


class KnowledgeSource(TimestampMixin, Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        Index("ix_knowledge_sources_profile_kb", "monitor_profile_id", "knowledge_base_id"),
        Index("ix_knowledge_sources_checksum_kb", "knowledge_base_id", "checksum"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_profile_id: Mapped[int] = mapped_column(ForeignKey("monitor_profiles.id"), nullable=False, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    uri_or_path: Mapped[str] = mapped_column(String(500), default="")
    checksum: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[KnowledgeSourceStatus] = mapped_column(
        Enum(KnowledgeSourceStatus), default=KnowledgeSourceStatus.QUEUED, nullable=False
    )
    error_message: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")

    knowledge_base = relationship("KnowledgeBase")
