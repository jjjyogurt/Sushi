from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MonitorProfile(TimestampMixin, Base):
    __tablename__ = "monitor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_user_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("app_users.id"),
        nullable=False,
        index=True,
        default="Sushi_1",
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    brand_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    markets: Mapped[str] = mapped_column(Text, nullable=False)
    languages: Mapped[str] = mapped_column(Text, nullable=False)
    key_products: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    alert_sensitivity: Mapped[str] = mapped_column(String(30), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    proactive_monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proactive_monitoring_cadence: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)
    unseen_monitoring_update_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_monitoring_digest: Mapped[str] = mapped_column(Text, default="", nullable=False)
    monitoring_updates_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
