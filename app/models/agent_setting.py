from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AgentSetting(TimestampMixin, Base):
    __tablename__ = "agent_settings"

    user_id: Mapped[str] = mapped_column(String(80), ForeignKey("app_users.id"), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    settings_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    user = relationship("AppUser")
