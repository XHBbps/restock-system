"""在途数据表（其他出库列表驱动）。

同步策略（spec FR-017a~d）：
- 每次同步记录 sync_start_time
- 对备注含"在途中"的出库单 UPSERT in_transit_record (is_in_transit=true, last_seen_at=sync_start_time)
- 同步结束后将 last_seen_at < sync_start_time 的活跃记录标记为 is_in_transit=false
  （代表"在途中"标签已消失，自动归零）
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class InTransitRecord(Base):
    """出库单级追踪记录。"""

    __tablename__ = "in_transit_record"
    __table_args__ = (
        Index(
            "ix_in_transit_record_active",
            "is_in_transit",
            "target_country",
            postgresql_where="is_in_transit = true",
        ),
        Index("ix_in_transit_record_last_seen", "last_seen_at"),
    )

    saihu_out_record_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    out_warehouse_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_warehouse_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("warehouse.id"), nullable=True
    )
    target_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)

    is_in_transit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class InTransitItem(Base):
    """出库单明细（SKU 级在途数量）。"""

    __tablename__ = "in_transit_item"
    __table_args__ = (
        Index("ix_in_transit_item_record", "saihu_out_record_id"),
        Index("ix_in_transit_item_sku", "commodity_sku"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    saihu_out_record_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("in_transit_record.saihu_out_record_id", ondelete="CASCADE"),
        nullable=False,
    )
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    # goods = 赛狐 "可用数" 字段 = SKU 的在途数量
    goods: Mapped[int] = mapped_column(Integer, nullable=False)
