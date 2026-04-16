"""Unit tests for suggestion API patch/push/delete endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.api.suggestion import delete_suggestion, patch_item, push_items
from app.core.exceptions import ConflictError, NotFound, PushBlockedError, ValidationFailed
from app.schemas.suggestion import PushRequest, SuggestionItemPatch


@dataclass
class _FakeResult:
    value: Any

    def scalar_one_or_none(self) -> Any:
        return self.value

    def first(self) -> Any:
        return self.value

    def scalars(self) -> _ScalarsProxy:
        return _ScalarsProxy(self.value)


class _ScalarsProxy:
    def __init__(self, values: Any) -> None:
        self._values = values if isinstance(values, list) else [values]

    def all(self) -> list[Any]:
        return list(self._values)


class _FakeSession:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.executed_statements: list[Any] = []

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        if _args:
            self.executed_statements.append(_args[0])
        return _FakeResult(self._results.pop(0))

    async def refresh(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _normalize_update_values(statement: Any) -> dict[str, Any]:
    return {
        getattr(key, "key", key): getattr(value, "value", value)
        for key, value in statement._values.items()
    }


class _FakeSuggestion:
    def __init__(self, status: str = "draft") -> None:
        self.id = 1
        self.status = status
        self.global_config_snapshot = {"lead_time_days": 20}


class _FakeItem:
    def __init__(self, push_status: str = "pending") -> None:
        self.id = 10
        self.suggestion_id = 1
        self.commodity_id: str | None = "CID-001"
        self.push_status = push_status
        self.push_blocker: str | None = None
        self.total_qty: int = 1
        self.country_breakdown: dict[str, int] = {"US": 1}
        self.warehouse_breakdown: dict[str, dict[str, int]] = {"US": {"W1": 1}}
        self.allocation_snapshot: dict[str, Any] | None = {"US": {"allocation_mode": "matched"}}
        self.sale_days_snapshot: dict[str, float] | None = {"US": 25.0}
        self.__dict__.setdefault("commodity_sku", "SKU-A")


async def test_suggestion_patch_archived_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(status="archived")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed, match=r"archived|归档"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_pushed_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(), _FakeItem(push_status="pushed")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed, match=r"pushed|推送"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_allows_country_sum_to_differ_from_total_qty(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    db = _FakeSession([_FakeSuggestion(), _FakeItem(), None])
    patch = SuggestionItemPatch(
        total_qty=10,
        country_breakdown={"US": 3, "UK": 4},
        warehouse_breakdown={"US": {"W1": 3}},
    )
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    update_stmt = db.executed_statements[-1]
    normalized_values = _normalize_update_values(update_stmt)
    assert normalized_values["total_qty"] == 10
    assert normalized_values["country_breakdown"] == {"US": 3, "UK": 4}


async def test_suggestion_patch_recomputes_urgent_from_sale_days_and_lead_time(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    item = _FakeItem()
    item.sale_days_snapshot = {"US": 20.0, "UK": 45.0}
    db = _FakeSession([_FakeSuggestion(), item, None])
    patch = SuggestionItemPatch(
        country_breakdown={"US": 2, "UK": 3},
        warehouse_breakdown={"US": {"W1": 2}},
    )
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    update_stmt = db.executed_statements[-1]
    normalized_values = _normalize_update_values(update_stmt)
    assert normalized_values["urgent"] is True


async def test_suggestion_patch_ignores_missing_sale_days_when_recomputing_urgent(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    item = _FakeItem()
    item.sale_days_snapshot = {"US": 25.0}
    db = _FakeSession([_FakeSuggestion(), item, None])
    patch = SuggestionItemPatch(
        country_breakdown={"US": 2, "UK": 3},
        warehouse_breakdown={"US": {"W1": 2}},
    )
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    update_stmt = db.executed_statements[-1]
    normalized_values = _normalize_update_values(update_stmt)
    assert normalized_values["urgent"] is False


async def test_suggestion_patch_rejects_warehouse_sum_mismatch() -> None:
    db = _FakeSession([_FakeSuggestion(), _FakeItem()])
    patch = SuggestionItemPatch(
        country_breakdown={"US": 3},
        warehouse_breakdown={"US": {"W1": 2}},
    )
    with pytest.raises(ValidationFailed, match="warehouse_breakdown"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_archived_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(status="archived")])
    req = PushRequest(item_ids=[10])
    with pytest.raises(ConflictError, match=r"archived|不可推送"):
        await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_pushed_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(status="pushed")])
    req = PushRequest(item_ids=[10])
    with pytest.raises(ConflictError, match=r"pushed|不可推送"):
        await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_rejects_already_pushed_items_in_partial() -> None:
    db = _FakeSession(
        [
            _FakeSuggestion(status="partial"),
            [_FakeItem(push_status="pushed"), _FakeItem(push_status="pending")],
        ]
    )
    req = PushRequest(item_ids=[10, 11])
    with pytest.raises(ConflictError, match=r"已推送|重复推送"):
        await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_rejects_zero_qty_items() -> None:
    item = _FakeItem()
    item.total_qty = 0
    db = _FakeSession([_FakeSuggestion(status="draft"), [item]])
    req = PushRequest(item_ids=[10])
    with pytest.raises(PushBlockedError, match="total_qty<=0"):
        await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_auto_resolves_missing_commodity_id_before_enqueue(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    item = _FakeItem(push_status="blocked")
    item.commodity_id = None
    item.push_blocker = "missing_commodity_id"
    db = _FakeSession([_FakeSuggestion(status="draft"), [item]])
    req = PushRequest(item_ids=[10])

    async def _fake_refresh(*_args: Any, **_kwargs: Any) -> set[int]:
        item.commodity_id = "CID-NEW"
        item.push_blocker = None
        item.push_status = "pending"
        return {item.id}

    enqueue_mock = AsyncMock(return_value=(321, False))
    monkeypatch.setattr(suggestion_module, "refresh_suggestion_item_pushability", _fake_refresh)
    monkeypatch.setattr(suggestion_module, "enqueue_task", enqueue_mock)

    result = await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]

    assert result == {"task_id": 321, "existing": False}
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.kwargs["dedupe_key"] == "push_saihu#1#10"
    assert enqueue_mock.await_args.kwargs["payload"] == {"suggestion_id": 1, "item_ids": [10]}


async def test_suggestion_push_normalizes_item_ids_for_payload_and_dedupe(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    item_a = _FakeItem()
    item_b = _FakeItem()
    item_b.id = 11
    db = _FakeSession([_FakeSuggestion(status="draft"), [item_b, item_a]])
    req = PushRequest(item_ids=[11, 10, 10])

    enqueue_mock = AsyncMock(return_value=(321, False))
    monkeypatch.setattr(suggestion_module, "enqueue_task", enqueue_mock)

    result = await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]

    assert result == {"task_id": 321, "existing": False}
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.kwargs["dedupe_key"] == "push_saihu#1#10,11"
    assert enqueue_mock.await_args.kwargs["payload"] == {"suggestion_id": 1, "item_ids": [10, 11]}


async def test_suggestion_delete_rejects_missing_row() -> None:
    db = _FakeSession([None])
    with pytest.raises(NotFound, match=r"不存在|NotFound"):
        await delete_suggestion(suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_delete_rejects_pushed_row() -> None:
    db = _FakeSession([_FakeSuggestion(status="pushed")])
    with pytest.raises(ConflictError, match=r"pushed|删除"):
        await delete_suggestion(suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["draft", "partial", "error", "archived"])
async def test_suggestion_delete_allows_non_pushed_rows(status: str) -> None:
    db = _FakeSession([_FakeSuggestion(status=status), None])

    await delete_suggestion(suggestion_id=1, db=db, _={})  # type: ignore[arg-type]

    delete_stmt = db.executed_statements[-1]
    assert delete_stmt.table.name == "suggestion"


def test_suggestion_item_patch_rejects_negative_country_breakdown():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="不可为负"):
        SuggestionItemPatch(country_breakdown={"US": -10, "JP": 5})


def test_suggestion_item_patch_rejects_negative_warehouse_breakdown():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="不可为负"):
        SuggestionItemPatch(warehouse_breakdown={"US": {"WH-1": -5}})


def test_suggestion_item_patch_accepts_zero_values():
    patch = SuggestionItemPatch(country_breakdown={"US": 0, "JP": 5})
    assert patch.country_breakdown == {"US": 0, "JP": 5}


async def test_suggestion_patch_clears_allocation_snapshot_on_allocation_edit(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    db = _FakeSession([_FakeSuggestion(), _FakeItem(), None, None])
    patch = SuggestionItemPatch(warehouse_breakdown={"US": {"W1": 1}})
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    update_stmt = db.executed_statements[-1]
    normalized_values = _normalize_update_values(update_stmt)
    assert normalized_values["allocation_snapshot"] is None
