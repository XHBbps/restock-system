"""任务运行表（队列 + 历史 + 进度合一）。

核心约束：同一 `dedupe_key` 在 pending/running 状态下最多一条
（通过部分唯一索引实现）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class TaskRun(Base):
    """任务运行记录。

    状态枚举：pending / running / success / failed / skipped / cancelled
    - pending：已入队等待 Worker 领取
    - running：Worker 持有租约执行中
    - success：业务正常完成
    - failed：业务失败或租约过期被 reaper 标记
    - skipped：scheduler 触发但同键已有活跃任务，留痕
    - cancelled：人工中止（为后续预留）
    """

    __tablename__ = "task_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','success','failed','skipped','cancelled')",
            name="status_enum",
        ),
        CheckConstraint(
            "trigger_source IN ('scheduler','manual')",
            name="trigger_source_enum",
        ),
        # ★ 核心约束：dedupe_key 在活跃状态下唯一
        Index(
            "uq_task_run_active_dedupe",
            "dedupe_key",
            unique=True,
            postgresql_where="status IN ('pending', 'running')",
        ),
        # pending 任务调度查询优化
        Index(
            "ix_task_run_pending_priority",
            "status",
            "priority",
            "created_at",
            postgresql_where="status = 'pending'",
        ),
        # 历史查询
        Index("ix_task_run_job_created", "job_name", "created_at"),
        # 僵尸任务回收查询
        Index(
            "ix_task_run_lease",
            "lease_expires_at",
            postgresql_where="status = 'running'",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    job_name: Mapped[str] = mapped_column(String(50), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    trigger_source: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # 进度
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    step_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Worker 租约
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
