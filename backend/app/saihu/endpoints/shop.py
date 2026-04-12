"""店铺列表接口封装。

POST /api/shop/pageList.json
入参:pageNo / pageSize
返回:店铺记录数组(id / name / sellerId / region / marketplaceId / status / adStatus)
"""

from collections.abc import AsyncIterator
from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/shop/pageList.json"


async def list_shops(page_size: int = 100) -> AsyncIterator[dict[str, Any]]:
    """分页迭代所有店铺。"""
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
