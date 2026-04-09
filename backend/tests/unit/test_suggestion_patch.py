"""Unit tests for PATCH /api/suggestions/{id}/items/{item_id} (N1 + H4).

Uses a lightweight stub in place of AsyncSession: only needs execute() to
return an object that supports scalar_one_or_none().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.api.suggestion import patch_item
from app.core.exceptions import ValidationFailed
from app.schemas.suggestion import SuggestionItemPatch


@dataclass
class _FakeResult:
    value: Any

    def scalar_one_or_none(self) -> Any:
        return self.value


class _FakeSession:
    """Fake Session that returns preset results in execute() call order."""

    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
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
        self.t_purchase: dict[str, str] = {}
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
