from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.snapshot import _validate_restock_snapshot_items


def _item(**overrides):
    defaults = {
        "id": 1,
        "country_breakdown": {"US": 10},
        "warehouse_breakdown": {"US": {"WH-1": 10}},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_restock_snapshot_validation_rejects_non_reportable_country() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_restock_snapshot_items([_item(country_breakdown={"ZZ": 10}, warehouse_breakdown={})])

    assert exc.value.status_code == 422
    assert "国家不可报表展示" in str(exc.value.detail)


def test_restock_snapshot_validation_rejects_dirty_quantity() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_restock_snapshot_items([_item(country_breakdown={"US": 10.5}, warehouse_breakdown={})])

    assert exc.value.status_code == 422
    assert "正整数" in str(exc.value.detail)


def test_restock_snapshot_validation_allows_missing_warehouse_split() -> None:
    _validate_restock_snapshot_items([_item(country_breakdown={"US": 10}, warehouse_breakdown={})])


def test_restock_snapshot_validation_rejects_split_sum_mismatch() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_restock_snapshot_items(
            [_item(country_breakdown={"US": 10}, warehouse_breakdown={"US": {"WH-1": 9}})]
        )

    assert exc.value.status_code == 422
    assert "仓库拆分合计" in str(exc.value.detail)
