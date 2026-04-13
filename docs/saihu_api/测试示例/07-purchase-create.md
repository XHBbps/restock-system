# Purchase Create

## Interface Info
- Source doc: `采购单创建.md`
- Method: `POST`
- URL path: `/api/purchase/create.json`
- Started at: `2026-04-08T10:05:06.7138514+08:00`
- Duration: `103 ms`
- HTTP status: `200`
- OpenAPI code: `40014`
- OpenAPI msg: `[includeTax] 是否含税操作行为不合法`
- requestId: `241dbd39-8671-4ea9-88ab-3f2238c6328e`
- ts: `1775613906497`

## Notes
- Invalid warehouseId and commodityId are intentionally used to avoid creating real purchase data.
- This report documents the real API behavior for that invalid-input call.

## Query Params
```json
{
    "access_token":  "b3d7...8b40",
    "client_id":  "368181",
    "timestamp":  "1775613906712",
    "nonce":  "45100",
    "sign":  "c456...7075"
}
```

## Body
```json
{
    "includeTax":  "false",
    "warehouseId":  "-1",
    "items":  [
                  {
                      "commodityId":  "-1",
                      "num":  "1"
                  }
              ],
    "action":  "1"
}
```

## Response
```json
{
    "code":  40014,
    "msg":  "[includeTax] 是否含税操作行为不合法",
    "data":  null,
    "ts":  1775613906497,
    "requestId":  "241dbd39-8671-4ea9-88ab-3f2238c6328e"
}
```
