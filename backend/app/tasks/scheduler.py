"""APScheduler 配置：定时入队任务（不直接执行业务）。

设计要点（spec FR-058a + analyze U3 修订）：
- AsyncIOScheduler，job_defaults={max_instances:1, coalesce:True, misfire_grace_time:60}
- 每个 cron 触发只调用 enqueue_task(...)，业务在 Worker 侧执行
- 调度配置：
  · 每小时一次：sync_product_listing / sync_inventory / sync_out_records / sync_order_list / sync_order_detail
  · 每日一次：sync_warehouse
  · 每日 02:00：daily_archive
  · cron 表达式：calc_engine（默认 08:00 Asia/Shanghai）
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.core.logging import get_logger
from app.core.timezone import BEIJING
from app.db.session import async_session_factory
from app.tasks.queue import enqueue_task

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _build_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(
        timezone=BEIJING,
        job_defaults={
            "max_instances": 1,
            "coalesce": True,
            "misfire_grace_time": 60,
        },
    )


async def _enqueue_safely(job_name: str) -> None:
    """scheduler 触发的入队动作，捕获所有异常避免影响其他 job。"""
    try:
        async with async_session_factory() as db:
            await enqueue_task(db, job_name=job_name, trigger_source="scheduler")
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler_enqueue_error", job_name=job_name, error=str(exc))


def setup_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    scheduler = _build_scheduler()

    interval = settings.default_sync_interval_minutes

    # 每小时同步组（按业务依赖顺序入队，由 worker 串行执行）
    hourly_jobs = [
        "sync_product_listing",
        "sync_inventory",
        "sync_out_records",
        "sync_order_list",
        "sync_order_detail",
    ]
    for job_name in hourly_jobs:
        scheduler.add_job(
            _enqueue_safely,
            trigger=IntervalTrigger(minutes=interval),
            args=[job_name],
            id=f"trigger_{job_name}",
            replace_existing=True,
        )

    # 每日仓库同步
    scheduler.add_job(
        _enqueue_safely,
        trigger=CronTrigger(hour=3, minute=30, timezone=BEIJING),
        args=["sync_warehouse"],
        id="trigger_sync_warehouse",
        replace_existing=True,
    )

    # 每日 02:00 库存归档
    scheduler.add_job(
        _enqueue_safely,
        trigger=CronTrigger(hour=2, minute=0, timezone=BEIJING),
        args=["daily_archive"],
        id="trigger_daily_archive",
        replace_existing=True,
    )

    # 每日 08:00 规则引擎
    scheduler.add_job(
        _enqueue_safely,
        trigger=CronTrigger.from_crontab(settings.default_calc_cron, timezone=BEIJING),
        args=["calc_engine"],
        id="trigger_calc_engine",
        replace_existing=True,
    )

    _scheduler = scheduler
    return scheduler


def start_scheduler() -> None:
    scheduler = setup_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_shutdown")
    _scheduler = None
