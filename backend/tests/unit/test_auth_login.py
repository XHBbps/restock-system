from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.exceptions import LoginLocked, Unauthorized


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def first(self):
        return self._value

    def scalar_one(self):
        return self._value


class _FakeDb:
    def __init__(self, users=None, attempts=None) -> None:
        self.users = users or {}
        self.attempts = attempts or {}
        self.commits = 0
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        params = stmt.compile().params
        if "source_key_1" in params:
            return _ScalarResult(self.attempts.get(params["source_key_1"]))
        if "username_1" in params:
            return _ScalarResult(self.users.get(params["username_1"]))

        table = getattr(stmt, "table", None)
        if table is not None and table.name == "login_attempt":
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
        users={
            "admin": SimpleNamespace(
                id=1,
                username="admin",
                display_name="管理员",
                password_hash="hash",
                is_active=True,
                perm_version=0,
                role_id=1,
                is_superadmin=True,
                role_name="管理员",
            )
        },
    )
    settings = SimpleNamespace(login_failed_max=3, login_lock_minutes=10, jwt_expires_hours=24)

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "now_beijing", lambda: now)
    monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: False)

    with pytest.raises(Unauthorized):
        await auth_module.login(
            auth_module.LoginRequest(username="admin", password="wrong"),
            _make_request("8.8.8.8"),
            db=db,
        )

    assert db.commits == 1
    assert db.attempts["ip:8.8.8.8"].failed_count == 1
    assert db.attempts["ip:8.8.8.8"].locked_until is None
    assert db.attempts["user:admin"].failed_count == 1
    assert db.attempts["user:admin"].locked_until is None


@pytest.mark.asyncio
async def test_login_locked_source_is_rejected(monkeypatch) -> None:
    import app.api.auth as auth_module

    now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    db = _FakeDb(
        attempts={
            "ip:8.8.8.8": SimpleNamespace(
                source_key="ip:8.8.8.8",
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
            auth_module.LoginRequest(username="admin", password="any"),
            _make_request("8.8.8.8"),
            db=db,
        )

    assert db.commits == 0


@pytest.mark.asyncio
async def test_login_locked_source_does_not_block_other_ip(monkeypatch) -> None:
    import app.api.auth as auth_module

    now = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    db = _FakeDb(
        users={
            "admin": SimpleNamespace(
                id=1,
                username="admin",
                display_name="管理员",
                password_hash="hash",
                is_active=True,
                perm_version=3,
                role_id=1,
                is_superadmin=True,
                role_name="管理员",
            )
        },
        attempts={
            "ip:8.8.8.8": SimpleNamespace(
                source_key="ip:8.8.8.8",
                failed_count=0,
                locked_until=now + timedelta(minutes=5),
            )
        },
    )
    settings = SimpleNamespace(login_failed_max=3, login_lock_minutes=10, jwt_expires_hours=24)

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "now_beijing", lambda: now)
    monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(
        auth_module,
        "create_access_token",
        lambda user_id, perm_version=0: f"token-{user_id}-{perm_version}",
    )

    result = await auth_module.login(
        auth_module.LoginRequest(username="admin", password="correct"),
        _make_request("8.8.4.4"),
        db=db,
    )

    assert result.access_token == "token-1-3"
    assert result.user.username == "admin"
    assert db.commits == 1
