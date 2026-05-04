"""Physical item grouping for equivalent SKUs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class PhysicalItemGroup(Base):
    """Equivalent inventory SKUs that represent the same stock component."""

    __tablename__ = "physical_item_group"
    __table_args__ = (
        UniqueConstraint("name", name="uq_physical_item_group_name"),
        Index("ix_physical_item_group_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    aliases: Mapped[list[PhysicalItemSkuAlias]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by=lambda: PhysicalItemSkuAlias.sku,
        lazy="selectin",
    )


class PhysicalItemSkuAlias(Base):
    """One SKU alias that points to a physical item group."""

    __tablename__ = "physical_item_sku_alias"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_physical_item_sku_alias_sku"),
        Index("ix_physical_item_sku_alias_group_id", "group_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("physical_item_group.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    group: Mapped[PhysicalItemGroup] = relationship(back_populates="aliases")
