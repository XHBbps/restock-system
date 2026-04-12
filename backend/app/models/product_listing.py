"""在线产品 listing 表(SKU x 店铺 x 站点)。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ProductListing(Base):
    """赛狐在线产品信息同步落库。

    维度:(shop_id, marketplace_id, seller_sku) 唯一。
    `day*_sale_num` 字段仅存储供对账参考,不参与 velocity 计算
    (velocity 从 order_item 聚合)。
    """

    __tablename__ = "product_listing"
    __table_args__ = (
        UniqueConstraint("shop_id", "marketplace_id", "seller_sku", name="uq_product_listing_key"),
        Index("ix_product_listing_sku_mkt", "commodity_sku", "marketplace_id"),
        Index("ix_product_listing_commodity_sku", "commodity_sku"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    commodity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    shop_id: Mapped[str] = mapped_column(String(50), nullable=False)
    marketplace_id: Mapped[str] = mapped_column(String(10), nullable=False)
    seller_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)

    commodity_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_image: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 仅对账参考
    day7_sale_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day14_sale_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day30_sale_num: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    online_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

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
