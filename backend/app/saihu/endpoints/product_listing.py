"""在线产品信息接口封装。

POST /api/order/api/product/pageList.json
关键参数:
- match=true 仅拉已配对产品
- onlineStatusList=['active'] 仅在售
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/order/api/product/pageList.json"
PageObserver = Callable[[int, int, int], Awaitable[None] | None]


async def list_product_listings(
    page_size: int = 100,
    only_matched: bool = True,
    only_active: bool = True,
    on_page: PageObserver | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """迭代已配对、在售的 listing。"""
    client = get_saihu_client()
    page_no = 1
    while True:
        body: dict[str, Any] = {
            "pageNo": str(page_no),
            "pageSize": str(page_size),
        }
        if only_matched:
            body["match"] = "true"
        if only_active:
            body["onlineStatusList"] = ["active"]

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
