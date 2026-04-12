"""全局配置(单行表)。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class GlobalConfig(Base):
    """单行全局参数表,`id` 永远为 1。"""

    __tablename__ = "global_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("include_tax IN ('0','1')", name="include_tax_enum"),
        CheckConstraint("shop_sync_mode IN ('all','specific')", name="shop_sync_mode_enum"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)

    # 规则引擎默认参数
    buffer_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    target_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # 调度
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    scheduler_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    calc_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    calc_cron: Mapped[str] = mapped_column(String(50), nullable=False, default="0 8 * * *")

    # 推送
    default_purchase_warehouse_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    include_tax: Mapped[str] = mapped_column(String(1), nullable=False, default="0")

    # 店铺同步模式
    shop_sync_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="all")

    # 登录
    login_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

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
