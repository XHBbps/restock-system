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


class _ScalarMaybeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
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
        "is_buyer_requested_cancel": False,
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
    assert result.items[0].package_sn == "PKG-1"
    assert not hasattr(result.items[0], "source")
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


@pytest.mark.asyncio
async def test_list_orders_sku_filter_does_not_match_package_sn() -> None:
    db = _FakeSession(
        [
            _ScalarResult(1),
            _RowsResult([_make_row()]),
            _AllResult([(101, 3)]),
            _AllResult([("SHOP-1", "ORDER-1", "订单处理")]),
        ]
    )

    await data_api.list_orders(
        date_from=None,
        date_to=None,
        country=None,
        shop_id=None,
        status=None,
        sku="SKU-1",
        page=1,
        page_size=20,
        sort_by=None,
        sort_order="desc",
        db=db,
        _=None,
    )

    compiled_sql = str(db.statements[0])
    assert "amazon_order_id" in compiled_sql
    assert "package_sn LIKE" not in compiled_sql


@pytest.mark.asyncio
async def test_list_orders_applies_platform_filter() -> None:
    db = _FakeSession(
        [
            _ScalarResult(1),
            _RowsResult([_make_row(order_platform="Amazon")]),
            _AllResult([(101, 1)]),
            _AllResult([("SHOP-1", "ORDER-1", "订单处理")]),
        ]
    )

    await data_api.list_orders(
        date_from=None,
        date_to=None,
        country=None,
        shop_id=None,
        platform="Amazon",
        status=None,
        sku=None,
        page=1,
        page_size=20,
        sort_by=None,
        sort_order="desc",
        db=db,
        _=None,
    )

    compiled_sql = str(db.statements[0])
    assert "order_header.order_platform = :order_platform_1" in compiled_sql


@pytest.mark.asyncio
async def test_list_order_platforms_returns_distinct_nonblank_sorted_values() -> None:
    db = _FakeSession([_AllResult([("Amazon",), ("Temu",), ("Walmart",)])])

    result = await data_api.list_order_platforms(db=db, _=None)

    assert result == ["Amazon", "Temu", "Walmart"]
    compiled_sql = str(db.statements[0])
    assert "SELECT DISTINCT trim(order_header.order_platform)" in compiled_sql
    assert "order_header.order_platform IS NOT NULL" in compiled_sql
    assert "trim(order_header.order_platform) != :trim_" in compiled_sql
    assert "ORDER BY trim(order_header.order_platform) ASC" in compiled_sql


@pytest.mark.asyncio
async def test_get_order_detail_defaults_to_package_source_and_package_sn_lookup() -> None:
    db = _FakeSession(
        [
            _ScalarMaybeResult(_make_row()),
            _RowsResult(
                [
                    SimpleNamespace(
                        order_item_id="ITEM-1",
                        commodity_sku="SKU-1",
                        seller_sku="SELLER-1",
                        quantity_ordered=2,
                        quantity_shipped=2,
                        quantity_unfulfillable=0,
                        refund_num=0,
                        item_price_currency="USD",
                        item_price_amount=Decimal("10.00"),
                    )
                ]
            ),
            _ScalarMaybeResult(
                SimpleNamespace(
                    postal_code="90210",
                    state_or_region="CA",
                    city="Los Angeles",
                    detail_address="1 Main St",
                    receiver_name="Alice",
                    fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=BEIJING),
                )
            ),
        ]
    )

    result = await data_api.get_order_detail(
        shop_id="SHOP-1",
        amazon_order_id="ORDER-1",
        package_sn="PKG-1",
        db=db,
        _=None,
    )

    assert result.package_sn == "PKG-1"
    assert result.shop_id == "SHOP-1"
    assert result.items[0].commodity_sku == "SKU-1"
    assert result.detail_fetched_at == datetime(2026, 4, 16, 12, 0, tzinfo=BEIJING)

    compiled_params = dict(db.statements[0].compile().params)
    assert "订单处理" in compiled_params.values()
