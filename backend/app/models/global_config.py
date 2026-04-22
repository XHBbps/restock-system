"""全局配置(单行表)。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class GlobalConfig(Base):
    """单行全局参数表,`id` 永远为 1。"""

    __tablename__ = "global_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("shop_sync_mode IN ('all','specific')", name="shop_sync_mode_enum"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)

    # 规则引擎默认参数
    buffer_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    target_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    safety_stock_days: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    restock_regions: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    eu_countries: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    # 调度
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    scheduler_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)

    # 店铺同步模式
    shop_sync_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="all")

    # 登录
    login_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 补货建议生成开关（首次导出自动 OFF，管理员手动 ON）
    suggestion_generation_enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("true")
    )
    generation_toggle_updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True
    )
    generation_toggle_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
