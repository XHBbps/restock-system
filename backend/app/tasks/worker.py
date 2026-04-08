"""Worker：原子领取 + 心跳续租 + 业务执行。

设计要点（spec FR-058a/d/e）：
- 每 worker 通过 `UPDATE ... FOR UPDATE SKIP LOCKED` 抢占下一条 pending 任务
- 抢占成功立即写 worker_id / started_at / heartbeat_at / lease_expires_at
- 业务执行期间 30s 续租
- 终态写入 finished_at + status
- 异常：失败 + error_msg；不会自动重新入队
"""

import asyncio
import os
import socket
import uuid
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.task_run import TaskRun
from app.tasks.jobs import JOB_REGISTRY, JobContext

logger = get_logger(__name__)


# 稳定可读的 worker 标识：host:pid:短 uuid
_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


class Worker:
    """单实例后台 worker。"""

    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            # ★ 不变式检查：心跳必须至少跑 2 次才到达租约过期点，否则一次心跳失败就被误杀
            settings = get_settings()
            lease_seconds = settings.worker_lease_minutes * 60
            heartbeat_seconds = settings.worker_heartbeat_seconds
            if heartbeat_seconds * 2 >= lease_seconds:
                raise RuntimeError(
                    f"worker heartbeat ({heartbeat_seconds}s) × 2 must be < lease "
                    f"({lease_seconds}s); otherwise the reaper will kill healthy workers. "
                    f"fix config: WORKER_HEARTBEAT_SECONDS < WORKER_LEASE_MINUTES*60/2"
                )
            self._stop.clear()
            self._task = asyncio.create_task(self._run_loop(), name="task-worker")
            logger.info("worker_started", worker_id=_WORKER_ID)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        logger.info("worker_stopped")

    async def _run_loop(self) -> None:
        settings = get_settings()
        while not self._stop.is_set():
            try:
                claimed = await self._claim_one()
                if claimed is None:
                    await asyncio.sleep(settings.worker_poll_interval_seconds)
                    continue
                await self._execute(claimed)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("worker_loop_error", error=str(exc))
                await asyncio.sleep(settings.worker_poll_interval_seconds)

    async def _claim_one(self) -> dict[str, Any] | None:
        """原子领取一条 pending 任务。"""
        settings = get_settings()
        lease_seconds = settings.worker_lease_minutes * 60

        sql = text(
            """
            UPDATE task_run
            SET status = 'running',
                worker_id = :worker_id,
                started_at = now(),
                heartbeat_at = now(),
                lease_expires_at = now() + make_interval(secs => :lease_seconds),
                attempt_count = attempt_count + 1
            WHERE id = (
                SELECT id FROM task_run
                WHERE status = 'pending'
                ORDER BY priority, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, job_name, payload, attempt_count
            """
        )
        async with async_session_factory() as db:
            row = (
                await db.execute(
                    sql,
                    {"worker_id": _WORKER_ID, "lease_seconds": lease_seconds},
                )
            ).mappings().first()
            await db.commit()
            if row is None:
                return None
            return dict(row)

    async def _execute(self, claimed: dict[str, Any]) -> None:
        task_id = claimed["id"]
        job_name = claimed["job_name"]
        payload = claimed["payload"] or {}

        handler = JOB_REGISTRY.get(job_name)
        if handler is None:
            await self._mark_failed(task_id, f"未注册的 job_name: {job_name}")
            return

        # 启动心跳续租
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id))
        try:
            ctx = JobContext(
                task_id=task_id,
                job_name=job_name,
                payload=payload,
                progress_setter=self._make_progress_setter(task_id),
            )
            await handler(ctx)
            await self._mark_success(task_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("task_failed", task_id=task_id, job_name=job_name)
            await self._mark_failed(task_id, str(exc))
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _heartbeat_loop(self, task_id: int) -> None:
        settings = get_settings()
        interval = settings.worker_heartbeat_seconds
        lease_seconds = settings.worker_lease_minutes * 60
        try:
            while True:
                await asyncio.sleep(interval)
                async with async_session_factory() as db:
                    await db.execute(
                        text(
                            """
                            UPDATE task_run
                            SET heartbeat_at = now(),
                                lease_expires_at = now() + make_interval(secs => :lease_seconds)
                            WHERE id = :id AND status = 'running'
                            """
                        ),
                        {"id": task_id, "lease_seconds": lease_seconds},
                    )
                    await db.commit()
        except asyncio.CancelledError:
            return

    def _make_progress_setter(self, task_id: int):
        async def setter(
            *,
            current_step: str | None = None,
            step_detail: str | None = None,
            total_steps: int | None = None,
        ) -> None:
            values: dict[str, Any] = {}
            if current_step is not None:
                values["current_step"] = current_step
            if step_detail is not None:
                values["step_detail"] = step_detail
            if total_steps is not None:
                values["total_steps"] = total_steps
            if not values:
                return
            async with async_session_factory() as db:
                await db.execute(
                    update(TaskRun).where(TaskRun.id == task_id).values(**values)
                )
                await db.commit()

        return setter

    async def _mark_success(self, task_id: int) -> None:
        async with async_session_factory() as db:
            await db.execute(
                update(TaskRun)
                .where(TaskRun.id == task_id)
                .values(status="success", finished_at=now_beijing())
            )
            await db.commit()

    async def _mark_failed(self, task_id: int, error: str) -> None:
        async with async_session_factory() as db:
            await db.execute(
                update(TaskRun)
                .where(TaskRun.id == task_id)
                .values(status="failed", error_msg=error[:5000], finished_at=now_beijing())
            )
            await db.commit()


_worker_instance: Worker | None = None


def get_worker() -> Worker:
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = Worker()
    return _worker_instance
