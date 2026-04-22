"""Singleton dashboard snapshot cache."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class DashboardSnapshot(Base):
    """Stores the latest rendered payload for the workspace dashboard."""

    __tablename__ = "dashboard_snapshot"
    __table_args__ = (
        CheckConstraint(
            "status IN ('empty','ready','refreshing','failed')",
            name="dashboard_snapshot_status_enum",
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="empty")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_refresh_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 失效标记：配置变更（如 eu_countries / restock_regions / target_days /
    # lead_time_days 等）后置 TRUE，下次 dashboard API 自动 enqueue 刷新任务。
    stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
