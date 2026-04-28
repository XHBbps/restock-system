"""多平台订单列表接口封装。

POST /api/multiplatform/order/list.json
多平台接口当前无可靠更新时间字段，同步任务按 purchase 时间滚动覆盖。
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/multiplatform/order/list.json"
PageObserver = Callable[[int, int, int], Awaitable[None] | None]


async def list_multiplatform_orders(
    *,
    date_start: str,
    date_end: str,
    date_type: str = "purchase",
    shop_ids: list[str] | None = None,
    page_size: int = 100,
    on_page: PageObserver | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """迭代多平台订单列表。"""

    client = get_saihu_client()
    page_no = 1
    while True:
        body: dict[str, Any] = {
            "startDate": date_start,
            "endDate": date_end,
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
