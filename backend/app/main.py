"""FastAPI 应用入口。

启动顺序（lifespan）：
1. configure_logging
2. ensure global_config 单行（首次启动写入 bcrypt(LOGIN_PASSWORD)）
3. 启动 Worker
4. 启动 Reaper
5. 启动 Scheduler
关闭顺序相反。
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api import auth as auth_api
from app.api import suggestion as suggestion_api
from app.api import sync as sync_api
from app.api import task as task_api
from app.pushback import purchase as _job_push  # noqa: F401
# 触发 @register 装饰器：导入所有 sync 模块以注册 job_name
from app.sync import inventory as _job_inv  # noqa: F401
from app.sync import order_detail as _job_od  # noqa: F401
from app.sync import order_list as _job_ol  # noqa: F401
from app.sync import out_records as _job_or  # noqa: F401
from app.sync import product_listing as _job_pl  # noqa: F401
from app.sync import shop as _job_shop  # noqa: F401
from app.sync import warehouse as _job_wh  # noqa: F401
from app.engine import calc_engine_job as _job_calc  # noqa: F401
from app.config import get_settings
from app.core.exceptions import BusinessError, SaihuAPIError
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.global_config import GlobalConfig
from app.tasks.reaper import get_reaper
from app.tasks.scheduler import shutdown_scheduler, start_scheduler
from app.tasks.worker import get_worker

logger = get_logger(__name__)


async def _ensure_global_config() -> None:
    """首次启动时写入 global_config 单行（含 bcrypt 密码哈希）。"""
    settings = get_settings()
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
            sync_interval_minutes=settings.default_sync_interval_minutes,
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

    worker = get_worker()
    reaper = get_reaper()
    worker.start()
    reaper.start()
    start_scheduler()

    logger.info("app_started")
    try:
        yield
    finally:
        logger.info("app_stopping")
        shutdown_scheduler()
        await reaper.stop()
        await worker.stop()
        logger.info("app_stopped")


app = FastAPI(
    title="赛狐补货计算工具",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ==================== 全局异常处理 ====================
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


# ==================== 路由 ====================
app.include_router(auth_api.router)
app.include_router(task_api.router)
app.include_router(suggestion_api.router)
app.include_router(sync_api.router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """健康检查（Docker HEALTHCHECK + Caddy 探活）。"""
    return {"status": "ok"}
