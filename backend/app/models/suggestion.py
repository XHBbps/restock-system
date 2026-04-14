"""建议单主表 + 条目表。"""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Suggestion(Base):
    """一次规则引擎运行产出的建议单。"""

    __tablename__ = "suggestion"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','partial','pushed','archived','error')",
            name="status_enum",
        ),
        Index("ix_suggestion_created_at", "created_at"),
        Index("ix_suggestion_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    global_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pushed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SuggestionItem(Base):
    """建议单条目:每行对应一个 commodity_sku 的完整补货建议。"""

    __tablename__ = "suggestion_item"
    __table_args__ = (
        CheckConstraint(
            "push_status IN ('pending','pushed','push_failed','blocked')",
            name="push_status_enum",
        ),
        Index("ix_suggestion_item_suggestion", "suggestion_id"),
        Index("ix_suggestion_item_sku", "commodity_sku"),
        Index(
            "ix_suggestion_item_urgent",
            "urgent",
            postgresql_where="urgent = true",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion.id", ondelete="CASCADE"),
        nullable=False,
    )

    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    commodity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    total_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    country_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warehouse_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    allocation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # 可追溯快照
    velocity_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sale_days_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 推送相关
    push_blocker: Mapped[str | None] = mapped_column(String(50), nullable=True)
    push_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    saihu_po_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    push_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    push_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
