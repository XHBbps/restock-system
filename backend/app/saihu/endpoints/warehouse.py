"""仓库列表接口封装。

POST /api/warehouseManage/warehouseList.json
"""

from collections.abc import AsyncIterator
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/warehouseManage/warehouseList.json"


async def list_warehouses(page_size: int = 100) -> AsyncIterator[dict[str, Any]]:
    client = get_saihu_client()
    page_no = 1
    while True:
        body = {"pageNo": str(page_no), "pageSize": str(page_size)}
        result = await client.post(ENDPOINT, body)
        data = result.get("data") or {}
        rows = data.get("rows") or []
        for row in rows:
            yield row
        total_page = int(data.get("totalPage") or 0)
        if page_no >= total_page or not rows:
            return
        page_no += 1
