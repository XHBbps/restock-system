"""订单相关表(order_header + order_item + order_detail + order_detail_fetch_log)。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

ORDER_SOURCE_AMAZON = "亚马逊"
ORDER_SOURCE_MULTIPLATFORM = "多平台"


class OrderHeader(Base):
    """订单骨架(列表接口同步)。

    时间字段(purchase_date, last_update_date)已按订单站点时区解析并转为
    Asia/Shanghai 存储。
    """

    __tablename__ = "order_header"
    __table_args__ = (
        UniqueConstraint("shop_id", "amazon_order_id", "source", name="uq_order_header_key"),
        Index("ix_order_header_purchase_date", "purchase_date"),
        Index("ix_order_header_country_purchase", "country_code", "purchase_date"),
        Index("ix_order_header_shop_purchase", "shop_id", "purchase_date"),
        Index("ix_order_header_status_purchase", "order_status", "purchase_date"),
        Index("ix_order_header_last_update", "last_update_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(50), nullable=False)
    amazon_order_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=ORDER_SOURCE_AMAZON)
    order_platform: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ORDER_SOURCE_AMAZON
    )
    marketplace_id: Mapped[str] = mapped_column(String(10), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    # EU 合并前的原始国家码（审计用，不对外暴露）
    original_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    order_status: Mapped[str] = mapped_column(String(30), nullable=False)
    order_total_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    order_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    fulfillment_channel: Mapped[str | None] = mapped_column(String(10), nullable=True)

    purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    is_buyer_requested_cancel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refund_status: Mapped[str | None] = mapped_column(String(10), nullable=True)

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


class OrderItem(Base):
    """订单明细(SKU 级)。

    PK = (order_id, order_item_id) 使订单状态更新时 UPSERT 稳定。
    """

    __tablename__ = "order_item"
    __table_args__ = (Index("ix_order_item_commodity_sku", "commodity_sku"),)

    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_header.id", ondelete="CASCADE"),
        primary_key=True,
    )
    order_item_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    seller_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_shipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_unfulfillable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refund_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    item_price_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    item_price_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)


class OrderDetail(Base):
    """订单详情(含邮编,仅对已配对 SKU 相关订单拉取)。"""

    __tablename__ = "order_detail"
    __table_args__ = (
        Index(
            "ix_order_detail_country_postal",
            "country_code",
            "postal_code",
            postgresql_where="postal_code IS NOT NULL",
        ),
    )

    shop_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    amazon_order_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=ORDER_SOURCE_AMAZON
    )

    postal_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    state_or_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderDetailFetchLog(Base):
    """订单详情已拉列表(避免重复调用 1 QPS 限流的详情接口)。"""

    __tablename__ = "order_detail_fetch_log"

    shop_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    amazon_order_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=ORDER_SOURCE_AMAZON
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saihu_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saihu_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
