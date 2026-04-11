from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.api.config import create_zipcode_rule, delete_zipcode_rule, patch_zipcode_rule
from app.core.exceptions import NotFound, ValidationFailed
from app.schemas.config import ZipcodeRuleIn


class _FakeResult:
    def __init__(self, value: Any = None, *, rowcount: int | None = None) -> None:
        self._value = value
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeDb:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.added: list[Any] = []
        self.executed_statements: list[Any] = []
        self.flushed = 0
        self.refreshed: list[Any] = []

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed_statements.append(stmt)
        result = self._results.pop(0)
        return result if isinstance(result, _FakeResult) else _FakeResult(result)

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, row: Any) -> None:
        self.refreshed.append(row)


def _body(**overrides: Any) -> ZipcodeRuleIn:
    payload = {
        "country": "JP",
        "prefix_length": 2,
        "value_type": "number",
        "operator": ">=",
        "compare_value": "50",
        "warehouse_id": "wh-jp",
        "priority": 10,
    }
    payload.update(overrides)
    return ZipcodeRuleIn(**payload)


def _rule_row(**overrides: Any) -> SimpleNamespace:
    payload = {
        "id": 1,
        "country": "JP",
        "prefix_length": 2,
        "value_type": "number",
        "operator": ">=",
        "compare_value": "50",
        "warehouse_id": "wh-jp",
        "priority": 10,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.mark.asyncio
async def test_create_zipcode_rule_rejects_missing_warehouse() -> None:
    db = _FakeDb([None])

    with pytest.raises(NotFound, match="仓库 wh-jp 不存在"):
        await create_zipcode_rule(_body(), db=db, _={})  # type: ignore[arg-type]

    assert db.added == []
    assert db.flushed == 0


@pytest.mark.asyncio
async def test_create_zipcode_rule_rejects_cross_country_warehouse() -> None:
    db = _FakeDb([SimpleNamespace(id="wh-jp", country="US")])

    with pytest.raises(ValidationFailed, match="不匹配"):
        await create_zipcode_rule(_body(), db=db, _={})  # type: ignore[arg-type]

    assert db.added == []
    assert db.flushed == 0


@pytest.mark.asyncio
async def test_patch_zipcode_rule_rejects_missing_rule() -> None:
    db = _FakeDb([None])

    with pytest.raises(NotFound, match="规则 1 不存在"):
        await patch_zipcode_rule(_body(), rule_id=1, db=db, _={})  # type: ignore[arg-type]

    assert db.refreshed == []


@pytest.mark.asyncio
async def test_patch_zipcode_rule_rejects_cross_country_warehouse() -> None:
    existing_rule = _rule_row()
    db = _FakeDb([existing_rule, SimpleNamespace(id="wh-us", country="US")])

    with pytest.raises(ValidationFailed, match="不匹配"):
        await patch_zipcode_rule(
            _body(warehouse_id="wh-us"),
            rule_id=1,
            db=db,
            _={},
        )  # type: ignore[arg-type]

    assert db.refreshed == []


@pytest.mark.asyncio
async def test_patch_zipcode_rule_rejects_missing_warehouse() -> None:
    existing_rule = _rule_row()
    db = _FakeDb([existing_rule, None])

    with pytest.raises(NotFound, match="仓库 wh-jp 不存在"):
        await patch_zipcode_rule(_body(), rule_id=1, db=db, _={})  # type: ignore[arg-type]

    assert db.refreshed == []


@pytest.mark.asyncio
async def test_patch_zipcode_rule_updates_and_refreshes() -> None:
    existing_rule = _rule_row(priority=20)
    db = _FakeDb([existing_rule, SimpleNamespace(id="wh-jp", country="JP"), _FakeResult(None)])

    result = await patch_zipcode_rule(_body(priority=20), rule_id=1, db=db, _={})  # type: ignore[arg-type]

    assert result.id == 1
    assert result.priority == 20
    assert db.refreshed == [existing_rule]


@pytest.mark.asyncio
async def test_delete_zipcode_rule_rejects_missing_rule() -> None:
    db = _FakeDb([_FakeResult(rowcount=0)])

    with pytest.raises(NotFound, match="规则 9 不存在"):
        await delete_zipcode_rule(rule_id=9, db=db, _={})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_delete_zipcode_rule_succeeds_when_row_exists() -> None:
    db = _FakeDb([_FakeResult(rowcount=1)])

    result = await delete_zipcode_rule(rule_id=9, db=db, _={})  # type: ignore[arg-type]

    assert result is None


class _FakeDbWithAutoId(_FakeDb):
    """_FakeDb variant that assigns id=1 on flush, simulating DB auto-increment."""

    async def flush(self) -> None:
        for row in self.added:
            if not hasattr(row, "id") or row.id is None:
                row.id = 1
        await super().flush()


@pytest.mark.asyncio
async def test_create_zipcode_rule_accepts_between_operator() -> None:
    db = _FakeDbWithAutoId([SimpleNamespace(id="wh-jp", country="JP")])

    body = ZipcodeRuleIn(
        country="JP",
        prefix_length=3,
        value_type="number",
        operator="between",
        compare_value="000-270, 500-700",
        warehouse_id="wh-jp",
        priority=15,
    )

    result = await create_zipcode_rule(body, db=db, _={})  # type: ignore[arg-type]

    assert db.added, "规则应被写入"
    assert db.added[0].operator == "between"
    assert db.added[0].compare_value == "000-270, 500-700"
    assert result.operator == "between"
