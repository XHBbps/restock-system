"""Unit tests for suggestion API patch/delete endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.suggestion import delete_suggestion, patch_item
from app.core.exceptions import NotFound, ValidationFailed
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
    def __init__(
        self,
        procurement_export_status: str = "pending",
        restock_export_status: str = "pending",
    ) -> None:
        self.id = 10
        self.suggestion_id = 1
        self.commodity_sku = "SKU-A"
        self.procurement_export_status = procurement_export_status
        self.restock_export_status = restock_export_status
        self.total_qty = 1
        self.country_breakdown = {"US": 1}
        self.warehouse_breakdown = {"US": {"W1": 1}}
        self.allocation_snapshot: dict[str, Any] | None = {"US": {"allocation_mode": "matched"}}
        self.sale_days_snapshot: dict[str, float] | None = {"US": 25.0}
        self.purchase_qty = 0
        self.purchase_date = None
        self.restock_dates: dict[str, str | None] = {}
        self.urgent = False


def test_suggestion_item_patch_rejects_negative_purchase_qty() -> None:
    """purchase_qty 必须 >=0，否则 Pydantic 校验直接拒绝。"""
    with pytest.raises(ValidationError):
        SuggestionItemPatch(purchase_qty=-1)


async def test_suggestion_patch_archived_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(status="archived")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_exported_item_still_editable(monkeypatch) -> None:
    """已导出的 item 仍允许编辑；编辑后下次导出会产生新 version（immutable 历史）。"""
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    db = _FakeSession([_FakeSuggestion(), _FakeItem(procurement_export_status="exported"), None])
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    # 不抛错，应该正常更新
    patch = SuggestionItemPatch(purchase_qty=50)
    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    update_stmt = db.executed_statements[-1]
    values = _normalize_update_values(update_stmt)
    assert values["purchase_qty"] == 50


async def test_suggestion_patch_recomputes_total_qty_from_country_breakdown(monkeypatch) -> None:
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
    assert normalized_values["total_qty"] == 7
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
    assert normalized_values["restock_dates"]["US"] is not None
    assert normalized_values["restock_dates"]["UK"] is not None


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
    assert normalized_values["restock_dates"]["US"] is not None
    assert normalized_values["restock_dates"]["UK"] is None


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
    with pytest.raises(NotFound):
        await delete_suggestion(suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["draft", "error", "archived"])
async def test_suggestion_delete_allows_rows_without_snapshots(status: str) -> None:
    db = _FakeSession([_FakeSuggestion(status=status), 0, None])

    await delete_suggestion(suggestion_id=1, db=db, _={})  # type: ignore[arg-type]

    delete_stmt = db.executed_statements[-1]
    assert delete_stmt.table.name == "suggestion"


def test_suggestion_item_patch_rejects_negative_country_breakdown():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SuggestionItemPatch(country_breakdown={"US": -10, "JP": 5})


def test_suggestion_item_patch_rejects_negative_warehouse_breakdown():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
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


async def test_suggestion_patch_urgent_boundary_sale_days_equals_lead_time(monkeypatch) -> None:
    """边界：sale_days == lead_time 时 urgent=True（has_urgent_sale_days 用 <=）。"""
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    item = _FakeItem()
    item.sale_days_snapshot = {"US": 20.0, "UK": 45.0}
    db = _FakeSession([_FakeSuggestion(), item, None])
    patch = SuggestionItemPatch(
        country_breakdown={"US": 5, "UK": 3},
        warehouse_breakdown={"US": {"W1": 5}},
    )
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    values = _normalize_update_values(db.executed_statements[-1])
    assert values["urgent"] is True


async def test_suggestion_patch_urgent_boundary_sale_days_above_lead_time(monkeypatch) -> None:
    """边界：sale_days > lead_time 对每个国家都成立 → urgent=False。"""
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    item = _FakeItem()
    item.sale_days_snapshot = {"US": 21.0, "UK": 30.0}
    db = _FakeSession([_FakeSuggestion(), item, None])
    patch = SuggestionItemPatch(
        country_breakdown={"US": 5, "UK": 3},
        warehouse_breakdown={"US": {"W1": 5}},
    )
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    values = _normalize_update_values(db.executed_statements[-1])
    assert values["urgent"] is False


async def test_suggestion_patch_urgent_ignores_zero_qty_country(monkeypatch) -> None:
    """qty=0 的国家不参与 urgent 判定（positive_qty_countries 过滤）。

    US qty=0 但 sale_days=5（紧急），UK qty=3 且 sale_days=45（充裕） → urgent=False。
    """
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _fake_lead_time(*_args: Any, **_kwargs: Any) -> int:
        return 20

    item = _FakeItem()
    item.sale_days_snapshot = {"US": 5.0, "UK": 45.0}
    db = _FakeSession([_FakeSuggestion(), item, None])
    patch = SuggestionItemPatch(
        country_breakdown={"US": 0, "UK": 3},
        warehouse_breakdown={"UK": {"W1": 3}},
    )
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)
    monkeypatch.setattr(suggestion_module, "_resolve_effective_lead_time_days", _fake_lead_time)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    values = _normalize_update_values(db.executed_statements[-1])
    assert values["urgent"] is False
