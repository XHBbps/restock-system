# Out Records

## Interface Info
- Source doc: `鍏朵粬鍑哄簱鍒楄〃椤?md`
- Method: `POST`
- URL path: `/api/warehouseInOut/outRecords.json`
- Started at: `2026-04-08T10:04:59.8278923+08:00`
- Duration: `209 ms`
- HTTP status: `200`
- OpenAPI code: `0`
- OpenAPI msg: ``
- requestId: `64870820-8d99-4f62-b78b-744ac8c110da`
- ts: `1775613899687`

## Notes
- pageSize=2 is used to keep the report readable.

## Query Params
```json
{
    "access_token":  "b3d7...8b40",
    "client_id":  "368181",
    "timestamp":  "1775613899826",
    "nonce":  "86480",
    "sign":  "ff4e...edb4"
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
    "msg":  "",
    "data":  {
                 "pageNo":  1,
                 "pageSize":  2,
                 "totalPage":  184,
                 "totalSize":  367,
                 "rows":  [
                              {
                                  "id":  "699094",
                                  "warehouseId":  "104306",
                                  "targetFbaWarehouseId":  "0",
                                  "outWarehouseNo":  "OB2604030001",
                                  "createId":  "170574",
                                  "updateTime":  "2026-04-07 21:39",
                                  "status":  "1",
                                  "type":  0,
                                  "typeName":  "其他出库",
                                  "items":  [
                                                {
                                                    "commodityId":  "1723152",
                                                    "commoditySku":  "sbgef",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "51",
                                                    "defective":  "0",
                                                    "perPurchase":  "265.77777778"
                                                },
                                                {
                                                    "commodityId":  "1634016",
                                                    "commoditySku":  "phxkbj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "90",
                                                    "defective":  "0",
                                                    "perPurchase":  "78.00000000"
                                                },
                                                {
                                                    "commodityId":  "1640920",
                                                    "commoditySku":  "zdxtc",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "120",
                                                    "defective":  "0",
                                                    "perPurchase":  "190.00000000"
                                                },
                                                {
                                                    "commodityId":  "1796889",
                                                    "commoditySku":  "cdgef",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "54",
                                                    "defective":  "0",
                                                    "perPurchase":  "210.00000000"
                                                },
                                                {
                                                    "commodityId":  "1864771",
                                                    "commoditySku":  "23CHNTM",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "35",
                                                    "defective":  "0",
                                                    "perPurchase":  "223.63063330"
                                                },
                                                {
                                                    "commodityId":  "1622279",
                                                    "commoditySku":  "1A-QZ4F-LS64",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "50",
                                                    "defective":  "0",
                                                    "perPurchase":  "184.11428571"
                                                },
                                                {
                                                    "commodityId":  "1617330",
                                                    "commoditySku":  "smwj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "87",
                                                    "defective":  "0",
                                                    "perPurchase":  "315.00000000"
                                                },
                                                {
                                                    "commodityId":  "2031333",
                                                    "commoditySku":  "16gzhjbt",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "39",
                                                    "defective":  "0",
                                                    "perPurchase":  "267.40940439"
                                                },
                                                {
                                                    "commodityId":  "2031317",
                                                    "commoditySku":  "16gzhjht",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "32",
                                                    "defective":  "0",
                                                    "perPurchase":  "266.60175439"
                                                },
                                                {
                                                    "commodityId":  "1609303",
                                                    "commoditySku":  "hskbj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "40",
                                                    "defective":  "0",
                                                    "perPurchase":  "265.95204009"
                                                },
                                                {
                                                    "commodityId":  "1647145",
                                                    "commoditySku":  "dmwjljz",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "40",
                                                    "defective":  "0",
                                                    "perPurchase":  "221.04367280"
                                                },
                                                {
                                                    "commodityId":  "1604241",
                                                    "commoditySku":  "DHTYYPJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "20",
                                                    "defective":  "0",
                                                    "perPurchase":  "179.31506849"
                                                },
                                                {
                                                    "commodityId":  "1603963",
                                                    "commoditySku":  "ZT-US-TKJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "20",
                                                    "defective":  "0",
                                                    "perPurchase":  "27.20463320"
                                                },
                                                {
                                                    "commodityId":  "2281298",
                                                    "commoditySku":  "xj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "10",
                                                    "defective":  "0",
                                                    "perPurchase":  "96.00000000"
                                                },
                                                {
                                                    "commodityId":  "1603938",
                                                    "commoditySku":  "HC-GOL-new",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "26",
                                                    "defective":  "0",
                                                    "perPurchase":  "212.00000000"
                                                },
                                                {
                                                    "commodityId":  "1622300",
                                                    "commoditySku":  "eddmwj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "80",
                                                    "defective":  "0",
                                                    "perPurchase":  "110.00000000"
                                                }
                                            ],
                                  "remark":  "20230331亚特兰散货出库"
                              },
                              {
                                  "id":  "689899",
                                  "warehouseId":  "104306",
                                  "targetFbaWarehouseId":  "0",
                                  "outWarehouseNo":  "OB2603310002",
                                  "createId":  "247370",
                                  "updateTime":  "2026-03-31 15:56",
                                  "status":  "1",
                                  "type":  0,
                                  "typeName":  "其他出库",
                                  "items":  [
                                                {
                                                    "commodityId":  "2011344",
                                                    "commoditySku":  "RB2MCCJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "30",
                                                    "defective":  "0",
                                                    "perPurchase":  "541.43448276"
                                                },
                                                {
                                                    "commodityId":  "1604241",
                                                    "commoditySku":  "DHTYYPJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "15",
                                                    "defective":  "0",
                                                    "perPurchase":  "179.31506849"
                                                },
                                                {
                                                    "commodityId":  "1622300",
                                                    "commoditySku":  "eddmwj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "60",
                                                    "defective":  "0",
                                                    "perPurchase":  "110.00000000"
                                                },
                                                {
                                                    "commodityId":  "1622279",
                                                    "commoditySku":  "1A-QZ4F-LS64",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "15",
                                                    "defective":  "0",
                                                    "perPurchase":  "184.11428571"
                                                },
                                                {
                                                    "commodityId":  "2204101",
                                                    "commoditySku":  "RBCCJ-hbs",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "15",
                                                    "defective":  "0",
                                                    "perPurchase":  "480.00000000"
                                                },
                                                {
                                                    "commodityId":  "1821497",
                                                    "commoditySku":  "55CM-TM",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "10",
                                                    "defective":  "0",
                                                    "perPurchase":  "217.00000000"
                                                },
                                                {
                                                    "commodityId":  "1603944",
                                                    "commoditySku":  "ZT-US-MJ-B03",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "30",
                                                    "defective":  "0",
                                                    "perPurchase":  "353.72670807"
                                                },
                                                {
                                                    "commodityId":  "1647145",
                                                    "commoditySku":  "dmwjljz",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "20",
                                                    "defective":  "0",
                                                    "perPurchase":  "221.04367280"
                                                },
                                                {
                                                    "commodityId":  "1922220",
                                                    "commoditySku":  "RBCCJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "50",
                                                    "defective":  "0",
                                                    "perPurchase":  "480.00000000"
                                                },
                                                {
                                                    "commodityId":  "1922887",
                                                    "commoditySku":  "RBJTJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "100",
                                                    "defective":  "0",
                                                    "perPurchase":  "285.00000000"
                                                },
                                                {
                                                    "commodityId":  "2281298",
                                                    "commoditySku":  "xj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "10",
                                                    "defective":  "0",
                                                    "perPurchase":  "96.00000000"
                                                },
                                                {
                                                    "commodityId":  "1796889",
                                                    "commoditySku":  "cdgef",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "50",
                                                    "defective":  "0",
                                                    "perPurchase":  "210.00000000"
                                                },
                                                {
                                                    "commodityId":  "1603950",
                                                    "commoditySku":  "HB-6CHBJ01",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "70",
                                                    "defective":  "0",
                                                    "perPurchase":  "45.00000000"
                                                },
                                                {
                                                    "commodityId":  "1603963",
                                                    "commoditySku":  "ZT-US-TKJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "30",
                                                    "defective":  "0",
                                                    "perPurchase":  "26.00000000"
                                                },
                                                {
                                                    "commodityId":  "1750316",
                                                    "commoditySku":  "bskbjcb",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "15",
                                                    "defective":  "0",
                                                    "perPurchase":  "73.55932203"
                                                },
                                                {
                                                    "commodityId":  "1609303",
                                                    "commoditySku":  "hskbj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "70",
                                                    "defective":  "0",
                                                    "perPurchase":  "265.95204009"
                                                },
                                                {
                                                    "commodityId":  "1773553",
                                                    "commoditySku":  "ygj",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "5",
                                                    "defective":  "0",
                                                    "perPurchase":  "310.00000000"
                                                },
                                                {
                                                    "commodityId":  "1821343",
                                                    "commoditySku":  "BS-SMKBJDGG",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "20",
                                                    "defective":  "0",
                                                    "perPurchase":  "187.24832215"
                                                },
                                                {
                                                    "commodityId":  "1750317",
                                                    "commoditySku":  "hskbjcb",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "30",
                                                    "defective":  "0",
                                                    "perPurchase":  "73.93750000"
                                                },
                                                {
                                                    "commodityId":  "1822844",
                                                    "commoditySku":  "WBQPJ",
                                                    "fnSku":  "",
                                                    "shopId":  0,
                                                    "shopName":  null,
                                                    "platform":  "OTHER",
                                                    "platformName":  null,
                                                    "goods":  "30",
                                                    "defective":  "0",
                                                    "perPurchase":  "90.10000000"
                                                }
                                            ],
                                  "remark":  ""
                              }
                          ]
             },
    "ts":  1775613899687,
    "requestId":  "64870820-8d99-4f62-b78b-744ac8c110da"
}
```
