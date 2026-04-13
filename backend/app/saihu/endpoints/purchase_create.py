"""采购单创建接口封装。

POST /api/purchase/create.json

必填字段(FR-045):
- warehouseId:主仓 ID
- action:操作行为,"1"=提交
- includeTax:含税标记,**字符串 "0"/"1"**(不是 true/false)
- items:采购明细,每条含 commodityId(赛狐内部商品ID)+ num(**字符串**)

其他字段(supplierId/partyaId 等)第一版不填,由赛狐 Web 端事后补全。
"""

from typing import Any

from app.saihu.client import get_saihu_client

ENDPOINT = "/api/purchase/create.json"


async def create_purchase_order(
    *,
    warehouse_id: str,
    items: list[dict[str, Any]],
    include_tax: str = "0",
    action: str = "1",
    custom_purchase_no: str | None = None,
    remark: str | None = None,
) -> list[dict[str, Any]]:
    """创建采购单。

    items: [{"commodityId": "2349630", "num": "928"}, ...]
    返回:赛狐返回的采购单对象数组(含 purchaseOrderNo)。
    """
    if include_tax not in ("0", "1"):
        raise ValueError("include_tax MUST be '0' or '1'")
    if action not in ("0", "1", "2"):
        raise ValueError("action MUST be '0' (草稿) / '1' (提交) / '2' (提交并下单)")

    body: dict[str, Any] = {
        "warehouseId": warehouse_id,
        "action": action,
        "includeTax": include_tax,
        "items": items,
    }
    if custom_purchase_no:
        body["customPurchaseNo"] = custom_purchase_no
    if remark:
        body["remark"] = remark

    client = get_saihu_client()
    result = await client.post(ENDPOINT, body, retry_network_errors=False)
    data = result.get("data") or []
    if not isinstance(data, list):
        return [data]
    return data
