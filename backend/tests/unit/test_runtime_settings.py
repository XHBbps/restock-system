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
    monkeypatch.setenv("JWT_SECRET", "strong-secret")
    monkeypatch.setenv("LOGIN_PASSWORD", "strong-password")
    monkeypatch.setenv("SAIHU_CLIENT_ID", "client")
    monkeypatch.setenv("SAIHU_CLIENT_SECRET", "secret")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.docs_enabled() is False
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
