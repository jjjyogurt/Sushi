from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocSkillVersion(TimestampMixin, Base):
    __tablename__ = "voc_skill_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    skill_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
