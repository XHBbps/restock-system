"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api import auth as auth_api
from app.api import auth_users as auth_users_api
from app.api import config as config_api
from app.api import data as data_api
from app.api import metrics as metrics_api
from app.api import monitor as monitor_api
from app.api import suggestion as suggestion_api
from app.api import sync as sync_api
from app.api import task as task_api
from app.config import get_settings
from app.core.exceptions import BusinessError, SaihuAPIError
from app.core.permission_sync import sync_permissions
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.engine import calc_engine_job as _job_calc  # noqa: F401
from app.models.global_config import GlobalConfig
from app.pushback import purchase as _job_push  # noqa: F401
from app.sync import all as _job_all  # noqa: F401
from app.sync import inventory as _job_inv  # noqa: F401
from app.sync import order_detail as _job_od  # noqa: F401
from app.sync import order_list as _job_ol  # noqa: F401
from app.sync import out_records as _job_or  # noqa: F401
from app.sync import product_listing as _job_pl  # noqa: F401
from app.sync import shop as _job_shop  # noqa: F401
from app.sync import warehouse as _job_wh  # noqa: F401
from app.tasks.jobs import daily_archive as _job_arch  # noqa: F401
from app.tasks.jobs import dashboard_snapshot as _job_dashboard_snapshot  # noqa: F401
from app.tasks.reaper import get_reaper
from app.tasks.scheduler import reload_scheduler, scheduler_status, shutdown_scheduler
from app.tasks.worker import get_worker

logger = get_logger(__name__)
settings = get_settings()


async def _ensure_global_config() -> None:
    """Seed the singleton global config row on first boot."""
    async with async_session_factory() as db:
        existing = (
            await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
        ).scalar_one_or_none()
        if existing is not None:
            return

        stmt = pg_insert(GlobalConfig).values(
            id=1,
            buffer_days=settings.default_buffer_days,
            target_days=settings.default_target_days,
            lead_time_days=settings.default_lead_time_days,
            restock_regions=[],
            sync_interval_minutes=settings.default_sync_interval_minutes,
            scheduler_enabled=True,
            calc_enabled=True,
            calc_cron=settings.default_calc_cron,
            include_tax="0",
            shop_sync_mode="all",
            login_password_hash=hash_password(settings.login_password),
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=[GlobalConfig.id])
        await db.execute(stmt)
        await db.commit()
        logger.info("global_config_seeded")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("app_starting")
    await _ensure_global_config()
    async with async_session_factory() as db:
        await sync_permissions(db)

    worker = get_worker()
    reaper = get_reaper()
    if settings.process_enable_worker:
        worker.start()
    if settings.process_enable_reaper:
        reaper.start()
    if settings.process_enable_scheduler:
        await reload_scheduler()

    logger.info("app_started")
    try:
        yield
    finally:
        logger.info("app_stopping")
        if settings.process_enable_scheduler:
            shutdown_scheduler(clear=True)
        if settings.process_enable_reaper:
            await reaper.stop()
        if settings.process_enable_worker:
            await worker.stop()
        logger.info("app_stopped")


app = FastAPI(
    title="Restock System",
    version="0.1.0",
    docs_url="/docs" if settings.docs_enabled() else None,
    openapi_url="/openapi.json" if settings.docs_enabled() else None,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
# 速率限制：每 IP 每分钟 60 个请求（公网暴露防御层）。
# 健康检查路径 (/healthz, /readyz) 豁免。内存存储，进程级独立。
app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)


@app.exception_handler(BusinessError)
async def _business_exc_handler(_: Request, exc: BusinessError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(SaihuAPIError)
async def _saihu_exc_handler(_: Request, exc: SaihuAPIError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "message": exc.message,
            "endpoint": exc.endpoint,
            "code": exc.code,
            "request_id": exc.request_id,
        },
    )


app.include_router(auth_api.router)
app.include_router(auth_users_api.router)
app.include_router(task_api.router)
app.include_router(suggestion_api.router)
app.include_router(sync_api.router)
app.include_router(config_api.router)
app.include_router(monitor_api.router)
app.include_router(metrics_api.router)
app.include_router(data_api.router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok"}


async def _database_ready() -> bool:
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("readiness_check_failed", error=str(exc))
        return False


async def _background_ready() -> tuple[bool, dict[str, bool]]:
    worker = get_worker()
    reaper = get_reaper()
    scheduler_ok = True
    if settings.process_enable_scheduler:
        status = await scheduler_status()
        scheduler_ok = (not status.enabled) or status.running
    components = {
        "worker": (not settings.process_enable_worker) or worker.running,
        "reaper": (not settings.process_enable_reaper) or reaper.running,
        "scheduler": scheduler_ok,
    }
    return all(components.values()), components


@app.get("/readyz", tags=["health"])
async def readyz() -> JSONResponse:
    """Readiness probe that verifies database and background services."""
    if not await _database_ready():
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": "database_unavailable"},
        )
    background_ok, components = await _background_ready()
    if not background_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "reason": "background_services_unavailable",
                "components": components,
            },
        )
    return JSONResponse(status_code=200, content={"status": "ok"})
