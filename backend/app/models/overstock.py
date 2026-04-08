"""积压 SKU 提示标记表。"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class OverstockSkuMark(Base):
    """库存 > 0 且全球 velocity = 0 的 (SKU, 国家, 仓库) 记录。"""

    __tablename__ = "overstock_sku_mark"
    __table_args__ = (
        UniqueConstraint(
            "commodity_sku",
            "country",
            "warehouse_id",
            name="uq_overstock_sku_mark_key",
        ),
        Index("ix_overstock_sku_mark_processed", "processed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(50), nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    last_sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
