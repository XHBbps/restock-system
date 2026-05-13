"""订单信息匹配确认导入文件暂存表。"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class OrderInfoMatchImportFile(Base):
    """保存确认导入后台任务消费的 Excel 二进制内容。"""

    __tablename__ = "order_info_match_import_file"
    __table_args__ = (
        Index("ix_order_info_match_import_file_expires", "expires_at"),
        Index("ix_order_info_match_import_file_task", "task_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def payload(self) -> dict[str, Any]:
        return {"filename": self.filename, "fields": self.fields}
