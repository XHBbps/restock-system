"""Third-party warehouse and inventory models."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ThirdPartyWarehouse(Base):
    """Manual third-party warehouse master data, independent of Saihu warehouses."""

    __tablename__ = "third_party_warehouse"
    __table_args__ = (
        UniqueConstraint("name", name="uq_third_party_warehouse_name"),
        Index("ix_third_party_warehouse_country", "country", postgresql_where="country IS NOT NULL"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ThirdPartyInventoryImportBatch(Base):
    """Import batch history and pending preview metadata."""

    __tablename__ = "third_party_inventory_import_batch"
    __table_args__ = (Index("ix_third_party_inventory_batch_status", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_warehouse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )


class ThirdPartyInventoryImportItem(Base):
    """Raw import row retained for preview and audit history."""

    __tablename__ = "third_party_inventory_import_item"
    __table_args__ = (
        Index("ix_third_party_inventory_item_batch", "batch_id"),
        Index("ix_third_party_inventory_item_warehouse", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("third_party_inventory_import_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("third_party_warehouse.id", ondelete="RESTRICT"),
        nullable=True,
    )
    commodity_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ThirdPartyInventoryCurrent(Base):
    """Current effective third-party inventory, editable by operators."""

    __tablename__ = "third_party_inventory_current"
    __table_args__ = (
        UniqueConstraint(
            "warehouse_id", "commodity_sku", name="uq_third_party_inventory_current_wh_sku"
        ),
        Index("ix_third_party_inventory_current_sku", "commodity_sku"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("third_party_warehouse.id", ondelete="RESTRICT"),
        nullable=False,
    )
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("third_party_inventory_import_batch.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_operation: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
