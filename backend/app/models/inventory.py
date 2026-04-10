"""库存快照表(latest 单行 + history 每日归档)。"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class InventorySnapshotLatest(Base):
    """最新库存快照(每次同步 UPSERT)。

    只存 `available` + `reserved`;在途数据由 in_transit_record/item 独立
    维护(spec FR-017 明确不读 stockWait)。
    """

    __tablename__ = "inventory_snapshot_latest"
    __table_args__ = (
        Index(
            "ix_inventory_latest_country_sku",
            "country",
            "commodity_sku",
        ),
    )

    commodity_sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("warehouse.id", ondelete="CASCADE"),
        primary_key=True,
    )
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class InventorySnapshotHistory(Base):
    """库存快照每日归档(02:00 由定时任务从 latest 表整表复制)。"""

    __tablename__ = "inventory_snapshot_history"
    __table_args__ = (
        Index("ix_inventory_history_date_sku", "snapshot_date", "commodity_sku"),
        Index("ix_inventory_history_sku_date", "commodity_sku", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
