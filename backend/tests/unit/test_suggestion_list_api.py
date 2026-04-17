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


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def execute(self, _statement):
        return self._responses.pop(0)


def _suggestion_row():
    return SimpleNamespace(
        id=1,
        status="draft",
        triggered_by="manual",
        total_items=10,
        pushed_items=2,
        failed_items=1,
        global_config_snapshot={},
        created_at=datetime(2026, 4, 17, 10, 0, 0),
        archived_at=None,
    )


@pytest.mark.asyncio
async def test_list_suggestions_returns_page_metadata() -> None:
    db = _FakeSession([_ScalarResult(1), _ScalarsResult([_suggestion_row()])])

    result = await list_suggestions(
        status=None,
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
