from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.commodity_id import (
    MISSING_COMMODITY_ID_BLOCKER,
    refresh_suggestion_item_pushability,
    resolve_commodity_id_map,
)


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def all(self) -> list[Any]:
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return self._value
        return [self._value]


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.executed: list[Any] = []

    async def execute(self, stmt: Any, *_args: Any, **_kwargs: Any) -> Any:
        self.executed.append(stmt)
        if self._responses:
            return self._responses.pop(0)
        return _ScalarResult(None)


def _normalize_update_values(statement: Any) -> dict[str, Any]:
    return {
        getattr(key, "key", key): getattr(value, "value", value)
        for key, value in statement._values.items()
    }


@pytest.mark.asyncio
async def test_resolve_commodity_id_map_falls_back_to_seller_sku() -> None:
    db = _FakeDb(
        [
            _ScalarResult([]),
            _ScalarResult([]),
            _ScalarResult([]),
            _ScalarResult([("SKU-A", "CID-FALLBACK")]),
        ]
    )

    result = await resolve_commodity_id_map(db, ["SKU-A"])

    assert result == {"SKU-A": "CID-FALLBACK"}


@pytest.mark.asyncio
async def test_refresh_suggestion_item_pushability_clears_blocker_when_resolved() -> None:
    item = SimpleNamespace(
        id=1,
        commodity_sku="SKU-A",
        commodity_id=None,
        push_blocker=MISSING_COMMODITY_ID_BLOCKER,
        push_status="blocked",
    )
    db = _FakeDb([_ScalarResult([("SKU-A", "CID-001")]), _ScalarResult(None)])

    updated_ids = await refresh_suggestion_item_pushability(db, [item])  # type: ignore[arg-type]

    assert updated_ids == {1}
    assert item.commodity_id == "CID-001"
    assert item.push_blocker is None
    assert item.push_status == "pending"
    normalized_values = _normalize_update_values(db.executed[-1])
    assert normalized_values == {
        "commodity_id": "CID-001",
        "push_blocker": None,
        "push_status": "pending",
    }


@pytest.mark.asyncio
async def test_refresh_suggestion_item_pushability_marks_unresolved_pending_item_as_blocked() -> None:
    item = SimpleNamespace(
        id=2,
        commodity_sku="SKU-B",
        commodity_id=None,
        push_blocker=None,
        push_status="pending",
    )
    db = _FakeDb([_ScalarResult([])])

    updated_ids = await refresh_suggestion_item_pushability(db, [item])  # type: ignore[arg-type]

    assert updated_ids == {2}
    assert item.push_blocker == MISSING_COMMODITY_ID_BLOCKER
    assert item.push_status == "blocked"
    normalized_values = _normalize_update_values(db.executed[-1])
    assert normalized_values == {
        "push_blocker": MISSING_COMMODITY_ID_BLOCKER,
        "push_status": "blocked",
    }
