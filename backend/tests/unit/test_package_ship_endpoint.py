from __future__ import annotations

import pytest


class _FakeSaihuClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    async def post(self, endpoint: str, body: dict[str, object]) -> dict[str, object]:
        self.requests.append((endpoint, body))
        return {
            "data": {
                "rows": [{"packageSn": "PKG-1"}],
                "totalPage": 1,
            }
        }


@pytest.mark.asyncio
async def test_list_package_ship_orders_uses_purchase_dates_and_page_size(monkeypatch) -> None:
    from app.saihu.endpoints import package_ship

    client = _FakeSaihuClient()
    monkeypatch.setattr(package_ship, "get_saihu_client", lambda: client)

    rows = [
        row
        async for row in package_ship.list_package_ship_orders(
            purchase_date_start="2025-04-29 10:00:00",
            purchase_date_end="2026-04-29 10:00:00",
            shop_ids=["SHOP-1"],
        )
    ]

    assert rows == [{"packageSn": "PKG-1"}]
    assert client.requests == [
        (
            "/api/packageShip/v1/getPackagePage.json",
            {
                "purchaseDateStart": "2025-04-29 10:00:00",
                "purchaseDateEnd": "2026-04-29 10:00:00",
                "pageNo": "1",
                "pageSize": "200",
                "shopIdList": ["SHOP-1"],
            },
        )
    ]
