from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.exceptions import LoginLocked, Unauthorized
from app.models.global_config import GlobalConfig
from app.models.login_attempt import LoginAttempt


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDb:
    def __init__(self, config, attempts=None) -> None:
        self.config = config
        self.attempts = attempts or {}
        self.commits = 0
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        if hasattr(stmt, "column_descriptions") and stmt.column_descriptions:
            entity = stmt.column_descriptions[0].get("entity")
            params = stmt.compile().params
            if entity is GlobalConfig:
                return _ScalarResult(self.config)
            if entity is LoginAttempt:
                source_key = next(iter(params.values()))
                return _ScalarResult(self.attempts.get(source_key))

        table = getattr(stmt, "table", None)
        if table is not None and table.name == "login_attempt":
            params = stmt.compile().params
            source_key = params.get("source_key") or params.get("source_key_1")
            attempt = self.attempts.get(source_key) or SimpleNamespace(
                source_key=source_key,
                failed_count=0,
                locked_until=None,
            )
            if "failed_count" in params:
                attempt.failed_count = params["failed_count"]
            if "locked_until" in params:
                attempt.locked_until = params["locked_until"]
            self.attempts[source_key] = attempt
        return _ScalarResult(None)

    async def commit(self) -> None:
        self.commits += 1


def _make_request(ip: str, headers=None):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=ip),
    )


@pytest.mark.asyncio
async def test_login_failed_password_records_attempt(monkeypatch) -> None:
    import app.api.auth as auth_module

    now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    db = _FakeDb(
        config=SimpleNamespace(login_password_hash="hash"),
    )
    settings = SimpleNamespace(login_failed_max=3, login_lock_minutes=10, jwt_expires_hours=24)

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "now_beijing", lambda: now)
    monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: False)

    with pytest.raises(Unauthorized):
        await auth_module.login(
            auth_module.LoginRequest(password="wrong"),
            _make_request("10.0.0.1"),
            db=db,
        )

    assert db.commits == 1
    assert db.attempts["ip:10.0.0.1"].failed_count == 1
    assert db.attempts["ip:10.0.0.1"].locked_until is None


@pytest.mark.asyncio
async def test_login_locked_source_is_rejected(monkeypatch) -> None:
    import app.api.auth as auth_module

    now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    db = _FakeDb(
        config=SimpleNamespace(login_password_hash="hash"),
        attempts={
            "ip:10.0.0.1": SimpleNamespace(
                source_key="ip:10.0.0.1",
                failed_count=0,
                locked_until=now + timedelta(minutes=5),
            )
        },
    )
    settings = SimpleNamespace(login_failed_max=3, login_lock_minutes=10, jwt_expires_hours=24)

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "now_beijing", lambda: now)

    with pytest.raises(LoginLocked):
        await auth_module.login(
            auth_module.LoginRequest(password="any"),
            _make_request("10.0.0.1"),
            db=db,
        )

    assert db.commits == 0


@pytest.mark.asyncio
async def test_login_locked_source_does_not_block_other_ip(monkeypatch) -> None:
    import app.api.auth as auth_module

    now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    db = _FakeDb(
        config=SimpleNamespace(login_password_hash="hash"),
        attempts={
            "ip:10.0.0.1": SimpleNamespace(
                source_key="ip:10.0.0.1",
                failed_count=0,
                locked_until=now + timedelta(minutes=5),
            )
        },
    )
    settings = SimpleNamespace(login_failed_max=3, login_lock_minutes=10, jwt_expires_hours=24)

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "now_beijing", lambda: now)
    monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(auth_module, "create_access_token", lambda: "token-123")

    result = await auth_module.login(
        auth_module.LoginRequest(password="correct"),
        _make_request("10.0.0.2"),
        db=db,
    )

    assert result.access_token == "token-123"
    assert db.commits == 0
