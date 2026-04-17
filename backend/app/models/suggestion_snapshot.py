"""建议单导出快照 + 快照条目。Immutable，不可删除。"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class SuggestionSnapshot(Base):
    """一次 Excel 导出操作产生的不可变快照。"""

    __tablename__ = "suggestion_snapshot"
    __table_args__ = (
        CheckConstraint(
            "generation_status IN ('generating','ready','failed')",
            name="generation_status_enum",
        ),
        UniqueConstraint("suggestion_id", "version", name="uq_snapshot_suggestion_version"),
        Index("ix_suggestion_snapshot_suggestion", "suggestion_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion.id", ondelete="CASCADE"),
        nullable=False,
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
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False)

    velocity_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sale_days_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 商品展示冻结
    commodity_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
