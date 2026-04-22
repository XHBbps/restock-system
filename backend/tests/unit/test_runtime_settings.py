import pytest

from app.config import get_settings


def test_production_settings_require_real_secrets(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
    )
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "please_change_me")
    monkeypatch.setenv("LOGIN_PASSWORD", "please_change_me")
    monkeypatch.setenv("SAIHU_CLIENT_ID", "")
    monkeypatch.setenv("SAIHU_CLIENT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Invalid application settings"):
        get_settings()

    get_settings.cache_clear()


def test_docs_disabled_by_default_in_production(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
    )
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "strong-secret-at-least-32-bytes!")
    monkeypatch.setenv("LOGIN_PASSWORD", "strong-password")
    monkeypatch.setenv("SAIHU_CLIENT_ID", "client")
    monkeypatch.setenv("SAIHU_CLIENT_SECRET", "secret")
    # 清掉 dev 容器继承的 APP_DOCS_ENABLED=true，防 env 泄漏污染默认值断言
    monkeypatch.delenv("APP_DOCS_ENABLED", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.docs_enabled() is False
    get_settings.cache_clear()


def test_docs_forced_off_in_production_even_if_env_tries_to_enable(monkeypatch) -> None:
    """安全边界：production 环境下即使 APP_DOCS_ENABLED=true 也必须返回 False。"""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
    )
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "strong-secret-at-least-32-bytes!")
    monkeypatch.setenv("LOGIN_PASSWORD", "strong-password")
    monkeypatch.setenv("SAIHU_CLIENT_ID", "client")
    monkeypatch.setenv("SAIHU_CLIENT_SECRET", "secret")
    # 即使显式设 true，production 也强制关
    monkeypatch.setenv("APP_DOCS_ENABLED", "true")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.docs_enabled() is False
    get_settings.cache_clear()


def test_docs_enabled_in_dev_by_default(monkeypatch) -> None:
    """dev 环境下默认开启 /docs。"""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
    )
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_DOCS_ENABLED", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.docs_enabled() is True
    get_settings.cache_clear()


def test_process_role_flags_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
    )
    monkeypatch.setenv("PROCESS_ENABLE_WORKER", "false")
    monkeypatch.setenv("PROCESS_ENABLE_REAPER", "false")
    monkeypatch.setenv("PROCESS_ENABLE_SCHEDULER", "true")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.process_enable_worker is False
    assert settings.process_enable_reaper is False
    assert settings.process_enable_scheduler is True
    get_settings.cache_clear()


def test_push_auto_retry_times_must_be_positive(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/replenish",
    )
    monkeypatch.setenv("PUSH_AUTO_RETRY_TIMES", "0")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="PUSH_AUTO_RETRY_TIMES must be >= 1"):
        get_settings()

    get_settings.cache_clear()
