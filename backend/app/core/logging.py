"""结构化日志（structlog JSON 输出）。

用法：
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("event_name", key=value)

在 `app.main` 启动时调用 `configure_logging()` 一次。
"""

import logging
import sys
from typing import Any

import structlog

from app.config import get_settings


def configure_logging() -> None:
    """全局配置 structlog + stdlib logging 转发。"""
    settings = get_settings()
    level = logging.getLevelName(settings.app_log_level.upper())

    # stdlib logging → 仅做输出载体，实际格式由 structlog 决定
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env == "development":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer(serializer=_safe_json_dumps))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """使用 orjson 序列化，回退 stdlib。"""
    try:
        import orjson

        return orjson.dumps(obj).decode("utf-8")
    except Exception:
        import json

        return json.dumps(obj, ensure_ascii=False, default=str)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取命名日志器。"""
    return structlog.get_logger(name)  # type: ignore[return-value]
