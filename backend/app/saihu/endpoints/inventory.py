"""库存明细接口封装。

POST /api/warehouseManage/warehouseItemList.json
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/warehouseManage/warehouseItemList.json"
PageObserver = Callable[[int, int, int], Awaitable[None] | None]


async def list_inventory_items(
    page_size: int = 100,
    warehouse_id: str | None = None,
    is_hidden: str | None = None,
    on_page: PageObserver | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """迭代库存明细。"""
    client = get_saihu_client()
    page_no = 1
    while True:
        body: dict[str, Any] = {
            "pageNo": str(page_no),
            "pageSize": str(page_size),
        }
        if warehouse_id:
            body["warehouseId"] = warehouse_id
        if is_hidden is not None:
            body["isHidden"] = is_hidden

        result = await client.post(ENDPOINT, body)
        data = result.get("data") or {}
        rows = data.get("rows") or []
        total_page = int(data.get("totalPage") or 0)
        if on_page is not None:
            page_event = on_page(page_no, total_page, len(rows))
            if page_event is not None:
                await page_event
        for row in rows:
            yield row
        if page_no >= total_page or not rows:
            return
        page_no += 1
