from __future__ import annotations

import pytest


class _FakeSaihuClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    async def post(self, endpoint: str, body: dict[str, object]) -> dict[str, object]:
        self.requests.append((endpoint, body))
        return {
            "data": {
                "rows": [{"orderNo": "ORDER-1"}],
                "totalPage": 1,
            }
        }


@pytest.mark.asyncio
async def test_list_multiplatform_orders_uses_documented_date_fields(monkeypatch) -> None:
    from app.saihu.endpoints import multiplatform_order

    client = _FakeSaihuClient()
    monkeypatch.setattr(multiplatform_order, "get_saihu_client", lambda: client)

    rows = [
        row
        async for row in multiplatform_order.list_multiplatform_orders(
            date_start="2026-03-29",
            date_end="2026-04-28",
            date_type="purchase",
            shop_ids=["SHOP-1"],
        )
    ]

    assert rows == [{"orderNo": "ORDER-1"}]
    assert client.requests == [
        (
            "/api/multiplatform/order/list.json",
            {
                "startDate": "2026-03-29",
                "endDate": "2026-04-28",
                "dateType": "purchase",
                "pageNo": "1",
                "pageSize": "100",
                "shopIdList": ["SHOP-1"],
            },
        )
    ]
