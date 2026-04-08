"""SQLAlchemy 声明基类。

所有 ORM 模型继承 `Base`。迁移文件 `alembic/env.py` 通过
`Base.metadata` 做 autogenerate 比对。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.sql import func

# 命名约定：让 Alembic 生成的约束名稳定可读
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有模型的基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: dict[type, Any] = {}


class TimestampMixin:
    """提供 created_at / updated_at，多数业务表会使用。"""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:  # noqa: N805
        from sqlalchemy import DateTime

        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:  # noqa: N805
        from sqlalchemy import DateTime

        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
