"""任务入队(事务化 + 部分唯一索引去重)。

行为(spec FR-058b/c):
- INSERT 时数据库部分唯一索引保证同 dedupe_key 在 pending/running 下唯一
- 捕获 UniqueViolation 即视为"已有活跃任务"
- scheduler 触发 -> 额外插入 status='skipped' 留痕
- manual 触发 -> 直接返回已有 task_id 供前端复用轮询
"""

from typing import Any

from asyncpg.exceptions import UniqueViolationError as AsyncpgUniqueViolation
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.task_run import TaskRun

logger = get_logger(__name__)


async def enqueue_task(
    db: AsyncSession,
    *,
    job_name: str,
    trigger_source: str,
    dedupe_key: str | None = None,
    payload: dict[str, Any] | None = None,
    priority: int = 100,
    _retry_depth: int = 0,
) -> tuple[int, bool]:
    """入队任务。

    返回 (task_id, is_existing):
    - is_existing=False 表示成功新建
    - is_existing=True 表示同键活跃任务已存在,返回的是它的 id
    """
    if trigger_source not in ("scheduler", "manual"):
        raise ValueError("trigger_source MUST be 'scheduler' or 'manual'")

    dedupe_key = dedupe_key or job_name
    payload = payload or {}

    try:
        result = await db.execute(
            insert(TaskRun)
            .values(
                job_name=job_name,
                dedupe_key=dedupe_key,
                trigger_source=trigger_source,
                priority=priority,
                payload=payload,
                status="pending",
            )
            .returning(TaskRun.id)
        )
        await db.commit()
        task_id = result.scalar_one()
        logger.info("task_enqueued", task_id=task_id, job_name=job_name, source=trigger_source)
        return task_id, False
    except IntegrityError as exc:
        await db.rollback()
        # 检查是不是部分唯一索引触发的冲突
        if not _is_dedupe_conflict(exc):
            raise

        existing = await db.execute(
            select(TaskRun.id)
            .where(TaskRun.dedupe_key == dedupe_key)
            .where(TaskRun.status.in_(("pending", "running")))
            .order_by(TaskRun.id.desc())
            .limit(1)
        )
        existing_id = existing.scalar_one_or_none()

        if existing_id is None:
            # 罕见竞争:唯一冲突但活跃记录又消失了,重试一次入队
            if _retry_depth >= 2:
                raise RuntimeError(
                    f"enqueue_task: 去重竞态重试耗尽 (job={job_name}, key={dedupe_key})"
                )
            logger.warning("task_enqueue_race_retry", job_name=job_name)
            return await enqueue_task(
                db,
                job_name=job_name,
                trigger_source=trigger_source,
                dedupe_key=dedupe_key,
                payload=payload,
                priority=priority,
                _retry_depth=_retry_depth + 1,
            )

        if trigger_source == "scheduler":
            # 留痕:插入一条 skipped 记录
            await db.execute(
                insert(TaskRun).values(
                    job_name=job_name,
                    dedupe_key=f"{dedupe_key}#skipped#{existing_id}",
                    trigger_source="scheduler",
                    priority=priority,
                    payload=payload,
                    status="skipped",
                    error_msg=f"Active task already exists: {existing_id}",
                )
            )
            await db.commit()

        logger.info(
            "task_dedupe_hit",
            existing_id=existing_id,
            job_name=job_name,
            source=trigger_source,
        )
        return existing_id, True


def _is_dedupe_conflict(exc: IntegrityError) -> bool:
    """识别 dedupe_key 冲突的部分唯一索引违规。"""
    msg = str(exc.orig) if exc.orig else str(exc)
    return "uq_task_run_active_dedupe" in msg or isinstance(exc.orig, AsyncpgUniqueViolation)
