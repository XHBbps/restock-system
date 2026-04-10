"""SKU 业务配置。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class SkuConfig(Base):
    """SKU 级可覆盖参数。

    `lead_time_days` 为 NULL 表示使用全局参数;0 表示当天采购(有效值)。
    """

    __tablename__ = "sku_config"
    __table_args__ = (
        Index(
            "ix_sku_config_enabled",
            "enabled",
            postgresql_where="enabled = true",
        ),
    )

    commodity_sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
