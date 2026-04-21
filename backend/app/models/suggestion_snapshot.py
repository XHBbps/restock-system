"""建议单导出快照 + 快照条目。Immutable，不可删除。"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class SuggestionSnapshot(Base):
    """一次 Excel 导出操作产生的不可变快照。

    `snapshot_type` 区分采购单（procurement）和补货单（restock），
    两种类型的 version 独立递增。
    """

    __tablename__ = "suggestion_snapshot"
    __table_args__ = (
        CheckConstraint(
            "generation_status IN ('generating','ready','failed')",
            name="generation_status_enum",
        ),
        CheckConstraint(
            "snapshot_type IN ('procurement','restock')",
            name="snapshot_type_enum",
        ),
        UniqueConstraint(
            "suggestion_id",
            "snapshot_type",
            "version",
            name="uq_snapshot_suggestion_type_version",
        ),
        Index("ix_suggestion_snapshot_suggestion", "suggestion_id"),
        Index("ix_snapshot_type_suggestion", "snapshot_type", "suggestion_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="restock"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # 审计
    exported_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sys_user.id"), nullable=True
    )
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    exported_from_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # 内容元数据
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    global_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # 文件生成
    generation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="generating"
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 下载计数
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SuggestionSnapshotItem(Base):
    """Snapshot 内冻结的 item 数据。"""

    __tablename__ = "suggestion_snapshot_item"
    __table_args__ = (
        Index("ix_snapshot_item_snapshot", "snapshot_id"),
        Index("ix_snapshot_item_sku", "commodity_sku"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )

    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    country_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warehouse_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # 采购类型快照冻结的值；补货类型快照可为 NULL。
    purchase_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False)

    velocity_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sale_days_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 商品展示冻结
    commodity_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
