"""订单列表接口封装。

POST /api/order/pageList.json
增量同步使用 dateType=updateDateTime 捕获状态变化(FR-021)。
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/order/pageList.json"
PageObserver = Callable[[int, int, int], Awaitable[None] | None]


async def list_orders(
    *,
    date_start: str,
    date_end: str,
    date_type: str = "updateDateTime",
    shop_ids: list[str] | None = None,
    page_size: int = 100,
    on_page: PageObserver | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """迭代订单列表。

    date_start / date_end 格式:'YYYY-MM-DD HH:MM:SS'
    date_type:updateDateTime / createDateTime / purchase
    """
    client = get_saihu_client()
    page_no = 1
    while True:
        body: dict[str, Any] = {
            "dateStart": date_start,
            "dateEnd": date_end,
            "dateType": date_type,
            "pageNo": str(page_no),
            "pageSize": str(page_size),
        }
        if shop_ids:
            body["shopIdList"] = shop_ids

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
