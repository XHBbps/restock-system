"""邮编->仓库映射规则。"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ZipcodeRule(Base):
    """按 priority 升序匹配:首条命中即返回;全部未命中归"未知仓"。

    表达式:`pref(zip, prefix_length)` 按 value_type 转型后与 compare_value
    用 operator 比较。
    """

    __tablename__ = "zipcode_rule"
    __table_args__ = (
        CheckConstraint("value_type IN ('number','string')", name="value_type_enum"),
        CheckConstraint(
            "operator IN ('=','!=','>','>=','<','<=','contains','not_contains','between')",
            name="operator_enum",
        ),
        CheckConstraint("prefix_length BETWEEN 1 AND 10", name="prefix_length_range"),
        Index("ix_zipcode_rule_country_priority", "country", "priority"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    prefix_length: Mapped[int] = mapped_column(Integer, nullable=False)
    value_type: Mapped[str] = mapped_column(String(10), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    compare_value: Mapped[str] = mapped_column(String(200), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("warehouse.id"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
