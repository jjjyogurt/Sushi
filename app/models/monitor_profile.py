from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MonitorProfile(TimestampMixin, Base):
    __tablename__ = "monitor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    brand_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    markets: Mapped[str] = mapped_column(Text, nullable=False)
    languages: Mapped[str] = mapped_column(Text, nullable=False)
    alert_sensitivity: Mapped[str] = mapped_column(String(30), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

