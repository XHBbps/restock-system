"""库存明细接口封装。

POST /api/warehouseManage/warehouseItemList.json
"""

from collections.abc import AsyncIterator
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/warehouseManage/warehouseItemList.json"


async def list_inventory_items(
    page_size: int = 100,
    warehouse_id: str | None = None,
    is_hidden: str | None = None,
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
        for row in rows:
            yield row
        total_page = int(data.get("totalPage") or 0)
        if page_no >= total_page or not rows:
            return
        page_no += 1
