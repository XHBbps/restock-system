"""Unit tests for suggestion API endpoints (PATCH item + POST push).

Uses a lightweight stub in place of AsyncSession: only needs execute() to
return an object that supports scalar_one_or_none().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.api.suggestion import patch_item, push_items
from app.core.exceptions import ConflictError, ValidationFailed
from app.schemas.suggestion import PushRequest, SuggestionItemPatch


@dataclass
class _FakeResult:
    value: Any

    def scalar_one_or_none(self) -> Any:
        return self.value

    def first(self) -> Any:
        return self.value


class _FakeSession:
    """Fake Session that returns preset results in execute() call order."""

    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.executed_statements: list[Any] = []

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        if _args:
            self.executed_statements.append(_args[0])
        return _FakeResult(self._results.pop(0))

    async def refresh(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeSuggestion:
    def __init__(self, status: str = "draft") -> None:
        self.id = 1
        self.status = status


class _FakeItem:
    def __init__(self, push_status: str = "pending") -> None:
        self.id = 10
        self.suggestion_id = 1
        self.push_status = push_status
        self.total_qty: int = 1
        self.country_breakdown: dict[str, int] = {"US": 1}
        self.warehouse_breakdown: dict[str, dict[str, int]] = {"US": {"W1": 1}}
        self.allocation_snapshot: dict[str, Any] | None = {"US": {"allocation_mode": "matched"}}
        self.t_purchase: dict[str, str] = {"US": "2099-01-01"}
        self.t_ship: dict[str, str] = {"US": "2099-01-15"}
        self.__dict__.setdefault("commodity_sku", "SKU-A")


async def test_suggestion_patch_archived_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(status="archived")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed, match=r"archived|已归档"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_pushed_rejected() -> None:
    db = _FakeSession([_FakeSuggestion(), _FakeItem(push_status="pushed")])
    patch = SuggestionItemPatch(total_qty=5)
    with pytest.raises(ValidationFailed, match=r"pushed|已推送"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_sum_mismatch_rejected() -> None:
    """H4: reject when sum(country_breakdown) != total_qty."""
    db = _FakeSession([_FakeSuggestion(), _FakeItem()])
    patch = SuggestionItemPatch(total_qty=10, country_breakdown={"US": 3, "UK": 4})
    with pytest.raises(ValidationFailed, match="country_breakdown"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_requires_t_purchase_for_positive_countries() -> None:
    db = _FakeSession([_FakeSuggestion(), _FakeItem()])
    patch = SuggestionItemPatch(total_qty=7, country_breakdown={"US": 3, "UK": 4})
    with pytest.raises(ValidationFailed, match="t_purchase"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_requires_t_ship_for_positive_countries() -> None:
    item = _FakeItem()
    item.t_ship = {"US": "2099-01-15"}
    db = _FakeSession([_FakeSuggestion(), item])
    patch = SuggestionItemPatch(
        total_qty=7,
        country_breakdown={"US": 3, "UK": 4},
        t_purchase={"US": "2099-01-01", "UK": "2099-01-02"},
    )
    with pytest.raises(ValidationFailed, match="t_ship"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_patch_rejects_invalid_t_purchase_date() -> None:
    db = _FakeSession([_FakeSuggestion(), _FakeItem()])
    patch = SuggestionItemPatch(t_purchase={"US": "not-a-date"})
    with pytest.raises(ValidationFailed, match="t_purchase"):
        await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_archived_rejected() -> None:
    """push_items 必须拒绝对 archived 建议单的推送（防止重复采购单）。"""
    db = _FakeSession([_FakeSuggestion(status="archived")])
    req = PushRequest(item_ids=[10])
    with pytest.raises(ConflictError, match=r"archived|不可推送"):
        await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


async def test_suggestion_push_pushed_rejected() -> None:
    """push_items 必须拒绝对 pushed 建议单的重新推送（幂等保护）。"""
    db = _FakeSession([_FakeSuggestion(status="pushed")])
    req = PushRequest(item_ids=[10])
    with pytest.raises(ConflictError, match=r"pushed|不可推送"):
        await push_items(req=req, suggestion_id=1, db=db, _={})  # type: ignore[arg-type]


def test_suggestion_item_patch_rejects_negative_country_breakdown():
    """P0-3: country_breakdown 值不可为负。"""
    from pydantic import ValidationError

    from app.schemas.suggestion import SuggestionItemPatch

    with pytest.raises(ValidationError, match="不可为负"):
        SuggestionItemPatch(country_breakdown={"US": -10, "JP": 5})


def test_suggestion_item_patch_rejects_negative_warehouse_breakdown():
    """P0-3: warehouse_breakdown 嵌套值不可为负。"""
    from pydantic import ValidationError

    from app.schemas.suggestion import SuggestionItemPatch

    with pytest.raises(ValidationError, match="不可为负"):
        SuggestionItemPatch(warehouse_breakdown={"US": {"WH-1": -5}})


def test_suggestion_item_patch_accepts_zero_values():
    """P0-3: 零值是允许的(清零某国补货量)。"""
    from app.schemas.suggestion import SuggestionItemPatch

    patch = SuggestionItemPatch(country_breakdown={"US": 0, "JP": 5})
    assert patch.country_breakdown == {"US": 0, "JP": 5}


async def test_suggestion_patch_clears_allocation_snapshot_on_allocation_edit(monkeypatch) -> None:
    import app.api.suggestion as suggestion_module

    async def _fake_enrich_item(*_args: Any, **_kwargs: Any) -> None:
        return None

    db = _FakeSession([_FakeSuggestion(), _FakeItem(), None, None])
    patch = SuggestionItemPatch(warehouse_breakdown={"US": {"W1": 2}})
    monkeypatch.setattr(suggestion_module, "_enrich_item", _fake_enrich_item)

    await patch_item(patch=patch, suggestion_id=1, item_id=10, db=db, _={})  # type: ignore[arg-type]

    update_stmt = db.executed_statements[-1]
    normalized_values = {
        getattr(key, "key", key): value for key, value in update_stmt._values.items()
    }
    assert getattr(normalized_values["allocation_snapshot"], "value", None) is None
