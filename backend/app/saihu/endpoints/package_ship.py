"""Package shipment order list endpoint wrapper.

POST /api/packageShip/v1/getPackagePage.json
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/packageShip/v1/getPackagePage.json"
PageObserver = Callable[[int, int, int], Awaitable[None] | None]


async def list_package_ship_orders(
    *,
    purchase_date_start: str,
    purchase_date_end: str,
    shop_ids: list[str] | None = None,
    page_size: int = 200,
    on_page: PageObserver | None = None,
) -> AsyncIterator[dict[str, Any]]:
    client = get_saihu_client()
    page_no = 1
    while True:
        body: dict[str, Any] = {
            "purchaseDateStart": purchase_date_start,
            "purchaseDateEnd": purchase_date_end,
            "pageNo": str(page_no),
            "pageSize": str(page_size),
        }
        if shop_ids:
            body["shopIdList"] = shop_ids

        result = await client.post(ENDPOINT, body)
        data = result.get("data") or {}
        rows = data.get("rows") or data.get("list") or []
        total_page = int(data.get("totalPage") or 0)
        if on_page is not None:
            page_event = on_page(page_no, total_page, len(rows))
            if page_event is not None:
                await page_event
        for row in rows:
            if isinstance(row, dict):
                yield row
        if page_no >= total_page or not rows:
            return
        page_no += 1
