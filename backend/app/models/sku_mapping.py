"""SKU mapping rules from commodity SKU to inventory package SKUs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class SkuMappingRule(Base):
    """One commodity SKU mapping rule.

    Components define how many inventory/package SKUs are needed to assemble one
    unit of the commodity SKU.
    """

    __tablename__ = "sku_mapping_rule"
    __table_args__ = (
        UniqueConstraint("commodity_sku", name="uq_sku_mapping_rule_commodity_sku"),
        Index("ix_sku_mapping_rule_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
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

    components: Mapped[list[SkuMappingComponent]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by=lambda: (SkuMappingComponent.group_no, SkuMappingComponent.id),
        lazy="selectin",
    )


class SkuMappingComponent(Base):
    """Inventory SKU component within a mapping rule."""

    __tablename__ = "sku_mapping_component"
    __table_args__ = (
        UniqueConstraint(
            "rule_id", "inventory_sku", name="uq_sku_mapping_component_rule_inventory"
        ),
        Index("ix_sku_mapping_component_rule_id", "rule_id"),
        Index("ix_sku_mapping_component_rule_group", "rule_id", "group_no"),
        CheckConstraint("group_no > 0", name="ck_sku_mapping_component_group_no_positive"),
        CheckConstraint("quantity > 0", name="ck_sku_mapping_component_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sku_mapping_rule.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    inventory_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    rule: Mapped[SkuMappingRule] = relationship(back_populates="components")
