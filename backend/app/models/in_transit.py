"""Models for synced out-record tracking."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Index
from sqlalchemy.sql import func

from app.db.base import Base


class InTransitRecord(Base):
    """Out-record level tracking row from Saihu."""

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
    warehouse_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    out_warehouse_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_warehouse_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("warehouse.id"), nullable=True
    )
    target_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    update_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_in_transit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class InTransitItem(Base):
    """Out-record item row from Saihu."""

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
    commodity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    goods: Mapped[int] = mapped_column(Integer, nullable=False)
    per_purchase: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
