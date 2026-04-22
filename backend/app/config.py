"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "restock_backend"
    app_env: Literal["development", "production", "test"] = "development"
    app_timezone: str = "Asia/Shanghai"
    app_log_level: str = "INFO"
    app_docs_enabled: bool | None = None

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
        description="SQLAlchemy async DSN",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_recycle_seconds: int = 3600

    saihu_base_url: str = "https://openapi.sellfox.com"
    saihu_client_id: str = ""
    saihu_client_secret: str = ""
    saihu_request_timeout_seconds: float = 30.0
    saihu_max_retries: int = 3
    saihu_token_refresh_ahead_seconds: int = 300

    login_password: str = "please_change_me"
    jwt_secret: str = "please_change_me_32_byte_minimum_key!"
    jwt_algorithm: str = "HS256"
    jwt_expires_hours: int = 24
    login_failed_max: int = 5
    login_lock_minutes: int = 10

    process_enable_worker: bool = True
    process_enable_reaper: bool = True
    process_enable_scheduler: bool = True

    worker_poll_interval_seconds: float = 2.0
    worker_lease_minutes: int = 2
    worker_heartbeat_seconds: int = 30
    reaper_interval_seconds: int = 60

    push_auto_retry_times: int = 3
    push_max_items_per_batch: int = 50

    default_buffer_days: int = 30
    default_target_days: int = 60
    default_lead_time_days: int = 50
    default_calc_cron: str = "0 8 * * *"
    default_sync_interval_minutes: int = 60

    # Excel 导出文件根目录（相对 backend/ 或绝对路径）
    export_storage_dir: str = "../deploy/data/exports"

    # Retention 保留天数（04:00 daily cron 依据，0 表示永不过期）
    retention_task_run_days: int = 90
    retention_inventory_history_days: int = 180
    retention_exports_days: int = 60

    def docs_enabled(self) -> bool:
        # 生产环境强制关闭 /docs 与 /openapi.json，忽略 APP_DOCS_ENABLED env
        # override 以防止生产配置误开（安全优先于便利）。
        # dev / test 环境：APP_DOCS_ENABLED 明确设置时按之，否则默认开启。
        if self.app_env == "production":
            return False
        if self.app_docs_enabled is not None:
            return self.app_docs_enabled
        return True


def validate_settings(settings: Settings) -> Settings:
    """Fail fast for invalid runtime settings."""
    errors: list[str] = []

    if not settings.database_url.strip():
        errors.append("DATABASE_URL is required")

    if settings.worker_heartbeat_seconds * 2 >= settings.worker_lease_minutes * 60:
        errors.append("WORKER_HEARTBEAT_SECONDS must be less than WORKER_LEASE_MINUTES*60/2")
    if settings.push_auto_retry_times < 1:
        errors.append("PUSH_AUTO_RETRY_TIMES must be >= 1")
    if len(settings.jwt_secret.encode("utf-8")) < 32:
        errors.append("JWT_SECRET must be at least 32 bytes")

    if settings.app_env == "production":
        if settings.jwt_secret.strip() == "please_change_me_32_byte_minimum_key!":
            errors.append("JWT_SECRET must be replaced in production")
        if settings.login_password.strip() == "please_change_me":
            errors.append("LOGIN_PASSWORD must be replaced in production")
        if not settings.saihu_client_id.strip():
            errors.append("SAIHU_CLIENT_ID is required in production")
        if not settings.saihu_client_secret.strip():
            errors.append("SAIHU_CLIENT_SECRET is required in production")

    if errors:
        joined = "\n".join(f"- {message}" for message in errors)
        raise ValueError(f"Invalid application settings:\n{joined}")

    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached validated settings."""
    return validate_settings(Settings())
