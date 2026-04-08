"""其他出库列表接口封装（在途数据源）。

POST /api/warehouseInOut/outRecords.json
关键参数：searchField=remark, searchValue=在途中
"""

from collections.abc import AsyncIterator
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/warehouseInOut/outRecords.json"
IN_TRANSIT_KEYWORD = "在途中"


async def list_in_transit_records(page_size: int = 100) -> AsyncIterator[dict[str, Any]]:
    """迭代单据备注包含'在途中'的所有出库单。"""
    client = get_saihu_client()
    page_no = 1
    while True:
        body: dict[str, Any] = {
            "pageNo": str(page_no),
            "pageSize": str(page_size),
            "searchField": "remark",
            "searchValue": IN_TRANSIT_KEYWORD,
        }
        result = await client.post(ENDPOINT, body)
        data = result.get("data") or {}
        rows = data.get("rows") or []
        for row in rows:
            yield row
        total_page = int(data.get("totalPage") or 0)
        if page_no >= total_page or not rows:
            return
        page_no += 1
