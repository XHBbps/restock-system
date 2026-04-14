"""角色表。"""
from app.db.base import Base, TimestampMixin
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Role(TimestampMixin, Base):
    __tablename__ = "role"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
