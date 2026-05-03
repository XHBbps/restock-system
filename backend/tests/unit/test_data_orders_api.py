from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.api import data as data_api

BEIJING = ZoneInfo("Asia/Shanghai")


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _ScalarsWrapper:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _RowsResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarsWrapper(self._values)


class _AllResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self._responses.pop(0)


def _make_row(**overrides):
    payload = {
        "id": 101,
        "shop_id": "SHOP-1",
        "amazon_order_id": "ORDER-1",
        "source": "订单处理",
        "order_platform": "Amazon",
        "package_sn": "PKG-1",
        "package_status": "has_shipped",
        "shop_name": "Main Shop",
        "postal_code": "90210",
        "marketplace_id": "ATVPDKIKX0DER",
        "country_code": "US",
        "order_status": "Shipped",
        "order_total_currency": "USD",
        "order_total_amount": Decimal("10.00"),
        "fulfillment_channel": "AFN",
        "purchase_date": datetime(2026, 4, 16, 10, 0, tzinfo=BEIJING),
        "last_update_date": datetime(2026, 4, 16, 11, 0, tzinfo=BEIJING),
        "refund_status": None,
        "last_sync_at": datetime(2026, 4, 16, 11, 30, tzinfo=BEIJING),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.mark.asyncio
async def test_list_orders_applies_shop_filter_and_returns_paginated_payload() -> None:
    db = _FakeSession(
        [
            _ScalarResult(1),
            _RowsResult([_make_row(shop_id="SHOP-2")]),
            _AllResult([(101, 3)]),
            _AllResult([("SHOP-2", "ORDER-1", "订单处理")]),
        ]
    )

    result = await data_api.list_orders(
        date_from=None,
        date_to=None,
        country=None,
        shop_id="SHOP-2",
        status=None,
        sku=None,
        page=2,
        page_size=20,
        sort_by=None,
        sort_order="desc",
        db=db,
        _=None,
    )

    assert result.total == 1
    assert result.page == 2
    assert result.page_size == 20
    assert len(result.items) == 1
    assert result.items[0].shop_id == "SHOP-2"
    assert result.items[0].item_count == 3
    assert result.items[0].has_detail is True

    compiled_sql = str(db.statements[0])
    assert "order_header.shop_id = :shop_id_1" in compiled_sql

    detail_sql = str(db.statements[3])
    assert (
        "SELECT order_detail.shop_id, order_detail.amazon_order_id, order_detail.source"
        in detail_sql
    )


@pytest.mark.asyncio
async def test_list_orders_skips_page_followup_queries_when_empty() -> None:
    db = _FakeSession(
        [
            _ScalarResult(0),
            _RowsResult([]),
        ]
    )

    result = await data_api.list_orders(
        date_from=None,
        date_to=None,
        country=None,
        shop_id=None,
        status=None,
        sku=None,
        page=1,
        page_size=50,
        sort_by=None,
        sort_order="desc",
        db=db,
        _=None,
    )

    assert result.total == 0
    assert result.items == []
    assert len(db.statements) == 2
