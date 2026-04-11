"""订单详情接口封装。

POST /api/order/detailByOrderId.json
返回包含 postalCode / countryCode / stateOrRegion / detailAddress(实测)。
"""

from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/order/detailByOrderId.json"


async def get_order_detail(*, shop_id: str, amazon_order_id: str) -> dict[str, Any]:
    """获取单个订单详情。"""
    client = get_saihu_client()
    body = {"shopId": shop_id, "amazonOrderId": amazon_order_id}
    result = await client.post(ENDPOINT, body)
    data = result.get("data") or {}
    return data
