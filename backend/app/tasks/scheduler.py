"""APScheduler 配置：定时入队任务，不直接执行具体业务。"""

from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import get_settings
from app.core.logging import get_logger
from app.core.timezone import BEIJING
from app.db.session import async_session_factory
from app.models.global_config import GlobalConfig
from app.schemas.sync import SchedulerJobOut, SchedulerStatusOut
from app.tasks.queue import enqueue_task

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None
_scheduler_signature: tuple[int, str, bool] | None = None


@dataclass(frozen=True)
class SchedulerRuntimeConfig:
    enabled: bool
    sync_interval_minutes: int
    calc_cron: str
    calc_enabled: bool


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
    try:
        async with async_session_factory() as db:
            await enqueue_task(db, job_name=job_name, trigger_source="scheduler")
    except Exception as exc:
        logger.exception("scheduler_enqueue_error", job_name=job_name, error=str(exc))


async def _load_scheduler_config() -> SchedulerRuntimeConfig:
    settings = get_settings()
    async with async_session_factory() as db:
        row = (
            await db.execute(
                select(
                    GlobalConfig.scheduler_enabled,
                    GlobalConfig.sync_interval_minutes,
                    GlobalConfig.calc_cron,
                    GlobalConfig.calc_enabled,
                ).where(GlobalConfig.id == 1)
            )
        ).one_or_none()
    if row is None:
        return SchedulerRuntimeConfig(
            enabled=True,
            sync_interval_minutes=settings.default_sync_interval_minutes,
            calc_cron=settings.default_calc_cron,
            calc_enabled=True,
        )
    return SchedulerRuntimeConfig(
        enabled=bool(row.scheduler_enabled),
        sync_interval_minutes=int(row.sync_interval_minutes),
        calc_cron=str(row.calc_cron),
        calc_enabled=bool(row.calc_enabled),
    )


def _register_jobs(
    scheduler: AsyncIOScheduler,
    *,
    sync_interval_minutes: int,
    calc_cron: str,
    calc_enabled: bool,
) -> None:
    interval = sync_interval_minutes
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

    scheduler.add_job(
        _enqueue_safely,
        trigger=CronTrigger(hour=3, minute=30, timezone=BEIJING),
        args=["sync_warehouse"],
        id="trigger_sync_warehouse",
        replace_existing=True,
    )

    scheduler.add_job(
        _enqueue_safely,
        trigger=CronTrigger(hour=2, minute=0, timezone=BEIJING),
        args=["daily_archive"],
        id="trigger_daily_archive",
        replace_existing=True,
    )

    if calc_enabled:
        scheduler.add_job(
            _enqueue_safely,
            trigger=CronTrigger.from_crontab(calc_cron, timezone=BEIJING),
            args=["calc_engine"],
            id="trigger_calc_engine",
            replace_existing=True,
        )
    else:
        try:
            scheduler.remove_job("trigger_calc_engine")
        except Exception:
            pass


async def setup_scheduler(force_reload: bool = False) -> AsyncIOScheduler:
    global _scheduler, _scheduler_signature
    config = await _load_scheduler_config()
    signature = (config.sync_interval_minutes, config.calc_cron, config.calc_enabled)
    if (
        _scheduler is not None
        and not force_reload
        and _scheduler_signature == signature
    ):
        return _scheduler

    if _scheduler is not None:
        shutdown_scheduler(clear=True)

    scheduler = _build_scheduler()
    _register_jobs(
        scheduler,
        sync_interval_minutes=config.sync_interval_minutes,
        calc_cron=config.calc_cron,
        calc_enabled=config.calc_enabled,
    )
    _scheduler = scheduler
    _scheduler_signature = signature
    return scheduler


async def get_scheduler() -> AsyncIOScheduler:
    return await setup_scheduler()


async def scheduler_status() -> SchedulerStatusOut:
    scheduler = await setup_scheduler()
    config = await _load_scheduler_config()
    jobs: list[SchedulerJobOut] = []
    for job in scheduler.get_jobs():
        job_name = str(job.args[0]) if job.args else job.id.removeprefix("trigger_")
        jobs.append(
            SchedulerJobOut(
                job_name=job_name,
                next_run_time=job.next_run_time.isoformat() if job.next_run_time else None,
            )
        )

    return SchedulerStatusOut(
        enabled=config.enabled,
        running=scheduler.running,
        timezone=str(BEIJING),
        sync_interval_minutes=config.sync_interval_minutes,
        calc_cron=config.calc_cron,
        jobs=jobs,
    )


async def reload_scheduler() -> SchedulerStatusOut:
    scheduler = await setup_scheduler(force_reload=True)
    config = await _load_scheduler_config()
    if config.enabled and not scheduler.running:
        scheduler.start()
        logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))
    return await scheduler_status()


async def start_scheduler() -> None:
    config = await _load_scheduler_config()
    if not config.enabled:
        return
    scheduler = await setup_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))


def shutdown_scheduler(*, clear: bool = False) -> None:
    global _scheduler, _scheduler_signature
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_shutdown")
    if clear:
        _scheduler = None
        _scheduler_signature = None
