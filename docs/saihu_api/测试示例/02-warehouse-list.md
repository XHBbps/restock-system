# Warehouse List

## Interface Info
- Source doc: `鏌ヨ浠撳簱鍒楄〃.md`
- Method: `POST`
- URL path: `/api/warehouseManage/warehouseList.json`
- Started at: `2026-04-08T10:04:56.0344535+08:00`
- Duration: `328 ms`
- HTTP status: `200`
- OpenAPI code: `0`
- OpenAPI msg: `success`
- requestId: `cc5c21cb-aea4-4560-95db-e9a5c6b70ac5`
- ts: `1775613896044`

## Notes
- pageSize=2 is used to keep the report readable.

## Query Params
```json
{
    "access_token":  "b3d7...8b40",
    "client_id":  "368181",
    "timestamp":  "1775613895998",
    "nonce":  "22048",
    "sign":  "3976...9736"
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
                 "totalPage":  32,
                 "totalSize":  64,
                 "rows":  [
                              {
                                  "id":  "104306",
                                  "shopId":  null,
                                  "type":  "0",
                                  "mode":  "0",
                                  "replenishSite":  "-",
                                  "name":  "默认仓库",
                                  "manager":  "-",
                                  "skuKind":  "84",
                                  "stockAvailable":  "16111",
                                  "stockDefective":  "0",
                                  "stockOccupy":  "0",
                                  "stockWait":  "3000",
                                  "stockAllNum":  "16111",
                                  "totalPurchase":  "3129333.72",
                                  "inventoryCost":  "3129333.72"
                              },
                              {
                                  "id":  "104878",
                                  "shopId":  null,
                                  "type":  "2",
                                  "mode":  "0",
                                  "replenishSite":  "-",
                                  "name":  "Jusper美国-北美仓",
                                  "manager":  "-",
                                  "skuKind":  "136",
                                  "stockAvailable":  "546",
                                  "stockDefective":  "1",
                                  "stockOccupy":  "76",
                                  "stockWait":  "408",
                                  "stockAllNum":  "623",
                                  "totalPurchase":  "36495.69",
                                  "inventoryCost":  "47134.73"
                              }
                          ]
             },
    "ts":  1775613896044,
    "requestId":  "cc5c21cb-aea4-4560-95db-e9a5c6b70ac5"
}
```
