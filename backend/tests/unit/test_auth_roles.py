from types import SimpleNamespace
from typing import Any

import pytest

from app.api.auth_roles import get_role_permissions, update_role_permissions
from app.api.deps import UserContext
from app.core.exceptions import BusinessError
from app.core.permissions import (
    ALL_CODES,
    AUTH_MANAGE,
    AUTH_VIEW,
    expand_permission_dependencies,
)
from app.schemas.auth import RolePermissionUpdate


class _FakeResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return list(self._value or [])


class _FakeDb:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.executed: list[Any] = []
        self.added: list[Any] = []
        self.committed = False

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        result = self._results.pop(0) if self._results else []
        return result if isinstance(result, _FakeResult) else _FakeResult(result)

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.committed = True


def _role(*, superadmin: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=2, name="operator", is_superadmin=superadmin)


def _perm_row(id_: int, code: str) -> SimpleNamespace:
    return SimpleNamespace(id=id_, code=code)


def _user(role_id: int = 2) -> UserContext:
    return UserContext(
        id=10,
        username="tester",
        display_name="Tester",
        role_id=role_id,
        role_name="operator",
        is_superadmin=False,
        perm_version=0,
    )


@pytest.mark.asyncio
async def test_update_role_permissions_expands_auth_manage_to_auth_view() -> None:
    db = _FakeDb(
        [
            _role(),
            [],
            [_perm_row(1, AUTH_VIEW), _perm_row(2, AUTH_MANAGE)],
        ]
    )

    await update_role_permissions(
        2,
        RolePermissionUpdate(permission_codes=[AUTH_MANAGE]),
        user=_user(),
        db=db,  # type: ignore[arg-type]
    )

    assert sorted(row.permission_id for row in db.added) == [1, 2]
    assert db.committed is True


def test_expand_permission_dependencies_adds_same_scope_view_when_available() -> None:
    expanded = expand_permission_dependencies(
        ["restock:operate", "restock:export", "restock:new_cycle", "history:delete"],
        ALL_CODES,
    )

    assert {"restock:view", "history:view"}.issubset(expanded)


def test_expand_permission_dependencies_keeps_operation_without_view() -> None:
    assert expand_permission_dependencies(["custom:edit"], {"custom:edit"}) == {"custom:edit"}


@pytest.mark.asyncio
async def test_update_role_permissions_keeps_operation_without_registered_view() -> None:
    db = _FakeDb([_role(), [], [_perm_row(9, "custom:edit")]])

    await update_role_permissions(
        2,
        RolePermissionUpdate(permission_codes=["custom:edit"]),
        user=_user(),
        db=db,  # type: ignore[arg-type]
    )

    assert [row.permission_id for row in db.added] == [9]
    assert db.committed is True


@pytest.mark.asyncio
async def test_update_role_permissions_no_change_does_not_bump_perm_version() -> None:
    db = _FakeDb(
        [
            _role(),
            [AUTH_VIEW, AUTH_MANAGE],
            [_perm_row(1, AUTH_VIEW), _perm_row(2, AUTH_MANAGE)],
        ]
    )

    await update_role_permissions(
        2,
        RolePermissionUpdate(permission_codes=[AUTH_MANAGE]),
        user=_user(),
        db=db,  # type: ignore[arg-type]
    )

    assert db.added == []
    assert db.committed is False
    assert len(db.executed) == 3


@pytest.mark.asyncio
async def test_update_role_permissions_changed_bumps_perm_version() -> None:
    db = _FakeDb(
        [
            _role(),
            [AUTH_VIEW],
            [_perm_row(1, AUTH_VIEW), _perm_row(2, AUTH_MANAGE)],
        ]
    )

    await update_role_permissions(
        2,
        RolePermissionUpdate(permission_codes=[AUTH_MANAGE]),
        user=_user(role_id=2),
        db=db,  # type: ignore[arg-type]
    )

    assert db.committed is True
    assert any(getattr(getattr(stmt, "table", None), "name", "") == "sys_user" for stmt in db.executed)


@pytest.mark.asyncio
async def test_get_superadmin_role_permissions_returns_active_codes() -> None:
    db = _FakeDb([_role(superadmin=True), [AUTH_VIEW, AUTH_MANAGE]])

    result = await get_role_permissions(1, db=db)  # type: ignore[arg-type]

    assert result == [AUTH_VIEW, AUTH_MANAGE]


@pytest.mark.asyncio
async def test_update_superadmin_role_permissions_rejected() -> None:
    db = _FakeDb([_role(superadmin=True)])

    with pytest.raises(BusinessError):
        await update_role_permissions(
            1,
            RolePermissionUpdate(permission_codes=[AUTH_MANAGE]),
            user=_user(),
            db=db,  # type: ignore[arg-type]
        )

    assert db.committed is False
