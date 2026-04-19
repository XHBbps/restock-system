"""Unit tests for suggestion API patch/push/delete endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import pytest

from app.api.suggestion import delete_suggestion, patch_item
from app.core.exceptions import ConflictError, NotFound, ValidationFailed
from app.schemas.suggestion import SuggestionItemPatch


@dataclass
class _FakeResult:
    value: Any

    def scalar_one_or_none(self) -> Any:
        return self.value

    def scalar_one(self) -> Any:
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
    def __init__(self, export_status: str = "pending") -> None:
        self.id = 10
        self.suggestion_id = 1
        self.commodity_sku: str = "SKU-A"
        self.export_status = export_status
        self.total_qty: int = 1
        self.country_breakdown: dict[str, int] = {"US": 1}
        self.warehouse_breakdown: dict[str, dict[str, int]] = {"US": {"W1": 1}}
        self.allocation_snapshot: dict[str, Any] | None = {"US": {"allocation_mode": "matched"}}
        self.sale_days_snapshot: dict[str, float] | None = {"US": 25.0}


async def test_suggestion_patch_archived_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(status="archived")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed, match=r"archived|归档"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_exported_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(), _FakeItem(export_status="exported")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed, match=r"exported|导出"):
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
    # Results: 1) suggestion lookup, 2) snapshot count (0), 3) delete execution
    db = _FakeSession([_FakeSuggestion(status=status), 0, None])

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
