from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.data import list_sku_overview


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _AllResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_sku_overview_returns_commodity_without_listing() -> None:
    sku_cfg = SimpleNamespace(commodity_sku="SKU-1", enabled=False, lead_time_days=None)
    commodity = SimpleNamespace(
        sku="SKU-1",
        commodity_id="CID-1",
        name="Master Product",
        img_url="https://example.test/master.jpg",
        state="active",
        is_group=False,
        purchase_days=12,
    )
    db = _FakeSession([_ScalarResult(1), _AllResult([(sku_cfg, commodity)]), _AllResult([])])

    result = await list_sku_overview(
        keyword="Master",
        enabled=False,
        page=1,
        page_size=50,
        db=db,
        _=None,
    )

    assert result.total == 1
    assert result.items[0].commodity_sku == "SKU-1"
    assert result.items[0].commodity_id == "CID-1"
    assert result.items[0].commodity_name == "Master Product"
    assert result.items[0].main_image == "https://example.test/master.jpg"
    assert result.items[0].purchase_days == 12
    assert result.items[0].has_listing is False
    assert result.items[0].listings == []
    assert "commodity_master" in str(db.statements[0])


@pytest.mark.asyncio
async def test_sku_overview_prefers_commodity_name_over_listing() -> None:
    sku_cfg = SimpleNamespace(commodity_sku="SKU-1", enabled=True, lead_time_days=30)
    commodity = SimpleNamespace(
        sku="SKU-1",
        commodity_id="CID-1",
        name="Master Product",
        img_url="https://example.test/master.jpg",
        state="active",
        is_group=True,
        purchase_days=None,
    )
    listing = SimpleNamespace(
        id=1,
        commodity_sku="SKU-1",
        commodity_name="Listing Product",
        main_image="https://example.test/listing.jpg",
        shop_id="SHOP-1",
        marketplace_id="US",
        seller_sku="SELLER-1",
        day7_sale_num=1,
        day14_sale_num=2,
        day30_sale_num=3,
        online_status="active",
        last_sync_at=datetime(2026, 5, 3, 10, 0, 0),
    )
    db = _FakeSession(
        [_ScalarResult(1), _AllResult([(sku_cfg, commodity)]), _AllResult([listing])]
    )

    result = await list_sku_overview(
        keyword=None,
        enabled=None,
        page=1,
        page_size=50,
        db=db,
        _=None,
    )

    item = result.items[0]
    assert item.commodity_name == "Master Product"
    assert item.main_image == "https://example.test/master.jpg"
    assert item.has_listing is True
    assert item.listing_count == 1
    assert item.total_day30_sales == 3
