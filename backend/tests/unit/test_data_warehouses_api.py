from datetime import datetime
from types import SimpleNamespace

from app.api.data import list_data_warehouses


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one(self):
        return self._value


class _RowsResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self._idx = 0

    async def execute(self, stmt):
        result = self._responses[self._idx]
        self._idx += 1
        return result


def _warehouse(**overrides):
    base = {
        "id": "WH-001",
        "name": "美国仓",
        "type": 3,
        "country": "US",
        "replenish_site_raw": "ATVPDKIKX0DER",
        "last_sync_at": datetime(2026, 4, 10, 12, 0, 0),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


async def test_list_data_warehouses_returns_total_stock() -> None:
    rows = [
        (_warehouse(id="WH-001", name="美国仓"), 30),
        (_warehouse(id="WH-002", name="英国仓", country="GB"), None),
    ]
    db = _FakeDb(
        [
            _ScalarResult(len(rows)),
            _RowsResult(rows),
        ]
    )

    result = await list_data_warehouses(page=1, page_size=500, db=db, _={})  # type: ignore[arg-type]

    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 500
    assert result.items[0].id == "WH-001"
    assert result.items[0].total_stock == 30
    assert result.items[1].id == "WH-002"
    assert result.items[1].total_stock == 0
