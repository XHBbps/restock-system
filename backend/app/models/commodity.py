"""Commodity master data synced from Saihu."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class CommodityMaster(Base):
    """Saihu commodity SKU master row.

    The primary key is Saihu's commodity SKU. Rows in this table describe SKU
    identity and display fields; they do not decide whether the replenishment
    engine should calculate the SKU.
    """

    __tablename__ = "commodity_master"
    __table_args__ = (
        Index("ix_commodity_master_state", "state"),
        Index("ix_commodity_master_is_group", "is_group"),
    )

    sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    commodity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    img_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    child_skus: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
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
