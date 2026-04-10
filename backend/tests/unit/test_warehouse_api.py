from datetime import datetime
from types import SimpleNamespace

from app.api.config import list_warehouses, patch_warehouse_country
from app.schemas.config import WarehouseCountryPatch


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _RowsResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0]


class _FakeDb:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.commits = 0

    async def execute(self, stmt):
        return self._responses.pop(0)

    async def commit(self) -> None:
        self.commits += 1


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


async def test_list_warehouses_returns_total_stock() -> None:
    db = _FakeDb(
        [
            _RowsResult(
                [
                    (_warehouse(id="WH-001", name="美国仓"), 18),
                    (_warehouse(id="WH-002", name="英国仓", country="GB"), None),
                ]
            )
        ]
    )

    rows = await list_warehouses(db=db, _={})  # type: ignore[arg-type]

    assert len(rows) == 2
    assert rows[0].id == "WH-001"
    assert rows[0].total_stock == 18
    assert rows[1].id == "WH-002"
    assert rows[1].total_stock == 0


async def test_patch_warehouse_country_returns_updated_total_stock() -> None:
    db = _FakeDb(
        [
            _ScalarResult(_warehouse()),
            _RowsResult([]),         # update Warehouse
            _RowsResult([]),         # update InventorySnapshotLatest
            _RowsResult([(_warehouse(country="CA"), 42)]),
        ]
    )

    result = await patch_warehouse_country(
        WarehouseCountryPatch(country="ca"),
        warehouse_id="WH-001",
        db=db,  # type: ignore[arg-type]
        _={},
    )

    assert db.commits == 1
    assert result.country == "CA"
    assert result.total_stock == 42
