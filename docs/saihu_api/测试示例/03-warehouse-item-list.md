# Warehouse Item List

## Interface Info
- Source doc: `查询库存明细.md`
- Method: `POST`
- URL path: `/api/warehouseManage/warehouseItemList.json`
- Started at: `2026-04-08T10:04:57.7816169+08:00`
- Duration: `626 ms`
- HTTP status: `200`
- OpenAPI code: `0`
- OpenAPI msg: `success`
- requestId: `78570ef6-62a0-41b9-9a6f-a2f06f3bcfaa`
- ts: `1775613898083`

## Notes
- pageSize=2 is used to keep the report readable.

## Query Params
```json
{
    "access_token":  "b3d7...8b40",
    "client_id":  "368181",
    "timestamp":  "1775613897780",
    "nonce":  "50064",
    "sign":  "f148...dce6"
}
```

## Body
```json
{
    "pageSize":  "2",
    "pageNo":  "1"
}
```

## Response
```json
{
    "code":  0,
    "msg":  "success",
    "data":  {
                 "pageNo":  1,
                 "pageSize":  2,
                 "totalPage":  491,
                 "totalSize":  982,
                 "rows":  [
                              {
                                  "id":  16744213,
                                  "createTime":  "2026-04-07 09:48:28",
                                  "updateTime":  "2026-04-07 12:15:35",
                                  "warehouseId":  "194735",
                                  "commodityId":  "2349630",
                                  "commoditySku":  "fsxhscjfj+23chntm",
                                  "commodityName":  "粉色小号假发架带头环+23寸黑女头模",
                                  "fnSku":  "",
                                  "platform":  "OTHER",
                                  "shopName":  null,
                                  "stockAvailable":  "16",
                                  "stockDefective":  "0",
                                  "stockOccupy":  null,
                                  "stockWait":  null,
                                  "stockPlan":  null,
                                  "stockAllNum":  "16",
                                  "perPurchase":  "410.0200",
                                  "totalPurchase":  "6560.3200",
                                  "onWayPurchase":  null,
                                  "perFee":  "0.0000",
                                  "totalFee":  "0.0000",
                                  "perInventoryCost":  "410.0200",
                                  "inventoryCost":  "6560.3200",
                                  "shipFee":  null,
                                  "otherFee":  null,
                                  "createId":  null,
                                  "updateId":  null
                              },
                              {
                                  "id":  16744207,
                                  "createTime":  "2026-04-07 09:48:28",
                                  "updateTime":  "2026-04-07 11:15:21",
                                  "warehouseId":  "153177",
                                  "commodityId":  "2349630",
                                  "commoditySku":  "fsxhscjfj+23chntm",
                                  "commodityName":  "粉色小号假发架带头环+23寸黑女头模",
                                  "fnSku":  "",
                                  "platform":  "OTHER",
                                  "shopName":  null,
                                  "stockAvailable":  "23",
                                  "stockDefective":  "0",
                                  "stockOccupy":  null,
                                  "stockWait":  null,
                                  "stockPlan":  null,
                                  "stockAllNum":  "23",
                                  "perPurchase":  "355.0000",
                                  "totalPurchase":  "8165.0000",
                                  "onWayPurchase":  null,
                                  "perFee":  "0.0000",
                                  "totalFee":  "0.0000",
                                  "perInventoryCost":  "355.0000",
                                  "inventoryCost":  "8165.0000",
                                  "shipFee":  null,
                                  "otherFee":  null,
                                  "createId":  null,
                                  "updateId":  null
                              }
                          ]
             },
    "ts":  1775613898083,
    "requestId":  "78570ef6-62a0-41b9-9a6f-a2f06f3bcfaa"
}
```
