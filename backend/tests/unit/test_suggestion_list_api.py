from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.suggestion import list_suggestions


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return self._responses.pop(0)


def _suggestion_row():
    return SimpleNamespace(
        id=1,
        status="draft",
        triggered_by="manual",
        total_items=10,
        procurement_item_count=4,
        restock_item_count=6,
        global_config_snapshot={},
        archived_trigger=None,
        created_at=datetime(2026, 4, 17, 10, 0, 0),
        archived_at=None,
    )


@pytest.mark.asyncio
async def test_list_suggestions_returns_page_metadata() -> None:
    db = _FakeSession(
        [
            _ScalarResult(1),
            _RowsResult([(_suggestion_row(), 2, 3)]),
        ]
    )

    result = await list_suggestions(
        status=None,
        display_status=None,
        date_from=None,
        date_to=None,
        sku=None,
        page=3,
        page_size=20,
        sort_by=None,
        sort_order="desc",
        db=db,
        _=None,
    )

    assert result.total == 1
    assert result.page == 3
    assert result.page_size == 20
    assert result.items[0].id == 1
    assert result.items[0].procurement_snapshot_count == 2
    assert result.items[0].restock_snapshot_count == 3


@pytest.mark.asyncio
async def test_list_suggestions_filters_derived_display_status_exported() -> None:
    db = _FakeSession(
        [
            _ScalarResult(0),
            _RowsResult([]),
        ]
    )

    await list_suggestions(
        status=None,
        display_status="exported",
        date_from=None,
        date_to=None,
        sku=None,
        page=1,
        page_size=20,
        sort_by=None,
        sort_order="desc",
        db=db,
        _=None,
    )

    compiled = db.executed[0].compile()
    sql_text = str(compiled)
    assert "suggestion.status" in sql_text
    assert "suggestion_snapshot" in sql_text
    assert compiled.params["status_1"] == "draft"
