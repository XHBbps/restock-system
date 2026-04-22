from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.models.in_transit import InTransitRecord


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None

    async def commit(self) -> None:
        return None


class _FakeScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeBackfillResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)


class _FakeBackfillDb:
    def __init__(self, rows: list[InTransitRecord]) -> None:
        self.rows = rows
        self.committed = False

    async def execute(self, _stmt: Any) -> _FakeBackfillResult:
        return _FakeBackfillResult(self.rows)

    async def commit(self) -> None:
        self.committed = True


def _statement_values(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_out_record_applies_eu_mapping_and_preserves_original_country() -> None:
    from app.sync.out_records import _upsert_out_record

    db = _FakeDb()
    await _upsert_out_record(
        db,  # type: ignore[arg-type]
        {
            "id": "OUT-EU-1",
            "warehouseId": "WH-SRC-1",
            "remark": "20260410\u5fb7\u56fd-\u8d62\u5d4e-\u5728\u9014\u4e2d",
            "items": [{"commoditySku": "SKU-1", "goods": "1"}],
        },
        set(),
        datetime(2026, 4, 14, 12, 0, 0),
        {"DE", "FR"},
    )

    record_values = _statement_values(db.statements[0])
    assert record_values["target_country"] == "EU"
    assert record_values["original_target_country"] == "DE"


@pytest.mark.asyncio
async def test_backfill_target_country_from_remark_applies_eu_mapping() -> None:
    from app.sync.out_records import _backfill_target_country_from_remark

    rows = [
        InTransitRecord(
            saihu_out_record_id="OUT-EU-1",
            remark="20260410\u5fb7\u56fd-\u8d62\u5d4e-\u7ebd\u7ea6-\u6563\u8d27-\u5728\u9014\u4e2d",
            target_country=None,
            is_in_transit=True,
            last_seen_at=datetime(2026, 4, 14, 12, 0, 0),
        ),
    ]
    db = _FakeBackfillDb(rows)

    scanned, updated, skipped = await _backfill_target_country_from_remark(
        db,  # type: ignore[arg-type]
        {"DE", "FR"},
    )

    assert scanned == 1
    assert updated == 1
    assert skipped == 0
    assert rows[0].target_country == "EU"
    assert rows[0].original_target_country == "DE"
