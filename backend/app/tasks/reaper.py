"""僵尸任务回收器（spec FR-058f）。

每 60s 运行一次：将 status='running' 且 lease_expires_at < now() 的
任务标记为 failed。回收后**不自动重新入队**，由业务侧决定是否触发新任务。
"""

import asyncio

from sqlalchemy import text

from app.config import get_settings
from app.core.logging import get_logger
from app.db.session import async_session_factory

logger = get_logger(__name__)


class Reaper:
    """租约过期回收器。"""

    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run_loop(), name="task-reaper")
            logger.info("reaper_started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        logger.info("reaper_stopped")

    async def _run_loop(self) -> None:
        settings = get_settings()
        while not self._stop.is_set():
            try:
                await self._reap_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("reaper_error", error=str(exc))
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=settings.reaper_interval_seconds
                )
            except asyncio.TimeoutError:
                pass

    async def _reap_once(self) -> None:
        async with async_session_factory() as db:
            result = await db.execute(
                text(
                    """
                    UPDATE task_run
                    SET status = 'failed',
                        error_msg = 'Lease expired, worker presumed dead',
                        finished_at = now()
                    WHERE status = 'running'
                      AND lease_expires_at < now()
                    RETURNING id
                    """
                )
            )
            ids = [row[0] for row in result.all()]
            await db.commit()
        if ids:
            logger.warning("reaper_collected_zombies", task_ids=ids)


_reaper_instance: Reaper | None = None


def get_reaper() -> Reaper:
    global _reaper_instance
    if _reaper_instance is None:
        _reaper_instance = Reaper()
    return _reaper_instance
