"""店铺表(赛狐 shop/pageList 结果缓存)。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Shop(Base):
    """店铺缓存。

    `status` 取值:0 正常 / 1 授权失效 / 2 SP授权失效。
    `sync_enabled` 由用户在"指定店铺模式"下勾选。
    """

    __tablename__ = "shop"
    __table_args__ = (Index("ix_shop_status", "status"),)

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    seller_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    marketplace_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    ad_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
