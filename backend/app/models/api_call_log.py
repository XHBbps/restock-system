"""赛狐接口调用日志(观测与监控)。"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ApiCallLog(Base):
    """赛狐 API 每次调用的结果日志。

    由 SaihuClient 在每次请求结束后写入(成功/失败都记录)。
    """

    __tablename__ = "api_call_log"
    __table_args__ = (
        Index("ix_api_call_log_endpoint_time", "endpoint", "called_at"),
        Index(
            "ix_api_call_log_failed",
            "called_at",
            postgresql_where="saihu_code IS NOT NULL AND saihu_code != 0",
        ),
        Index(
            "ix_api_call_log_retry_queue",
            "next_retry_at",
            "called_at",
            postgresql_where=(
                "saihu_code = 40019 AND retry_status = 'queued' "
                "AND request_payload IS NOT NULL AND retry_source_log_id IS NULL"
            ),
        ),
        Index("ix_api_call_log_retry_source", "retry_source_log_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saihu_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saihu_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    retry_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    auto_retry_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_retry_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_source_log_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("api_call_log.id", ondelete="SET NULL"),
        nullable=True,
    )
