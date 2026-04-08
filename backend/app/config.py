"""应用配置（pydantic-settings）。

所有配置从环境变量读取，单例通过 `get_settings()` 缓存。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全量运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 应用 ----------
    app_name: str = "restock_backend"
    app_env: Literal["development", "production", "test"] = "production"
    app_timezone: str = "Asia/Shanghai"
    app_log_level: str = "INFO"

    # ---------- 数据库 ----------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
        description="SQLAlchemy async DSN",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_recycle_seconds: int = 3600

    # ---------- 赛狐 API ----------
    saihu_base_url: str = "https://openapi.sellfox.com"
    saihu_client_id: str = ""
    saihu_client_secret: str = ""
    saihu_rate_limit_qps: float = 1.0
    saihu_request_timeout_seconds: float = 30.0
    saihu_max_retries: int = 3
    saihu_token_refresh_ahead_seconds: int = 300  # 提前 5 分钟续期

    # ---------- 鉴权 ----------
    login_password: str = "please_change_me"  # 首次启动种子密码
    jwt_secret: str = "please_change_me"
    jwt_algorithm: str = "HS256"
    jwt_expires_hours: int = 24
    login_failed_max: int = 5
    login_lock_minutes: int = 10

    # ---------- 任务系统 ----------
    worker_poll_interval_seconds: float = 2.0
    worker_lease_minutes: int = 2
    worker_heartbeat_seconds: int = 30
    reaper_interval_seconds: int = 60

    # ---------- 推送 ----------
    push_auto_retry_times: int = 3
    push_max_items_per_batch: int = 50

    # ---------- 规则引擎默认值 ----------
    default_buffer_days: int = 30
    default_target_days: int = 60
    default_lead_time_days: int = 50
    default_calc_cron: str = "0 8 * * *"
    default_sync_interval_minutes: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """缓存配置单例，测试可通过 `get_settings.cache_clear()` 重置。"""
    return Settings()
