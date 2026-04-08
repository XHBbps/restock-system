"""仓库表（赛狐同步 + 手动维护国家）。"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Warehouse(Base):
    """仓库主数据。

    `type` 取自赛狐：-1虚拟 / 0默认 / 1国内 / 2FBA / 3海外
    `country` 由采购员手动维护，未指定前不参与计算。
    """

    __tablename__ = "warehouse"
    __table_args__ = (
        Index("ix_warehouse_country", "country", postgresql_where="country IS NOT NULL"),
        Index("ix_warehouse_type", "type"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[int] = mapped_column(Integer, nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    replenish_site_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)

    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
