# Order Detail

## Interface Info
- Source doc: `璁㈠崟璇︽儏.md`
- Method: `POST`
- URL path: `/api/order/detailByOrderId.json`
- Started at: `2026-04-08T10:05:05.0416998+08:00`
- Duration: `263 ms`
- HTTP status: `200`
- OpenAPI code: `0`
- OpenAPI msg: ``
- requestId: `fc8c8106-81b9-4302-92e5-98f34cf5bee0`
- ts: `1775613904979`

## Notes
- Sample order selected from order-list response: shopId=325166, amazonOrderId=503-9019552-6582219
- This call is used to verify whether postalCode is returned in real data.
- postalCode returned in this sample: 640-8453

## Query Params
```json
{
    "access_token":  "b3d7...8b40",
    "client_id":  "368181",
    "timestamp":  "1775613905040",
    "nonce":  "95698",
    "sign":  "7bd6...bb12"
}
```

## Body
```json
{
    "amazonOrderId":  "503-9019552-6582219",
    "shopId":  "325166"
}
```

## Response
```json
{
    "code":  0,
    "msg":  "",
    "data":  {
                 "shopId":  "325166",
                 "amazonOrderId":  "503-9019552-6582219",
                 "sellerOrderId":  null,
                 "earliestShipDate":  null,
                 "providerName":  null,
                 "agentCat":  null,
                 "trackNo":  null,
                 "forwardNo":  null,
                 "orderStatus":  "Unshipped",
                 "orderTotalCurrency":  "JPY",
                 "orderTotalAmount":  "25000.0",
                 "marketplaceId":  "JP",
                 "orderType":  "StandardOrder",
                 "buyerName":  "藤田　泰成",
                 "buyerEmail":  "ydtnb1t2gk9npt6@marketplace.amazon.co.jp",
                 "receiverName":  "藤田　泰成",
                 "postalCode":  "640-8453",
                 "phone":  "09054644166",
                 "city":  null,
                 "county":  null,
                 "district":  null,
                 "stateOrRegion":  "和歌山県",
                 "countryCode":  "JP",
                 "detailAddress":  "和歌山市木ノ本1112-1 和歌山県 JP",
                 "comment":  null,
                 "orderItemVoList":  [
                                         {
                                             "orderItemId":  "14716273119005",
                                             "commoditySku":  "rb-30kgjtj",
                                             "title":  "Lhysn スチールラック プロ仕様 5 段 ガレージラック 総耐荷重800kg以上 大型 倉庫 車庫ラック 高さ調整可 組み立て簡単 頑丈安定 業務用家庭用 ガレージ/倉庫/オフィス収納 メタルラック 幅150×奥行50×高200cm ブラック",
                                             "asin":  "B0GL2BF1YZ",
                                             "sellerSku":  "150cm-fdjtj",
                                             "quantityOrdered":  "1",
                                             "quantityShipped":  "0",
                                             "quantityUnfulfillable":  null,
                                             "refundNum":  null,
                                             "refundAmount":  "0.000000",
                                             "itemPriceCurrency":  "JPY",
                                             "itemPriceAmount":  "25000.0",
                                             "imageUrl":  "https://m.media-amazon.com/images/I/51Fw13W7cmL._SL75_.jpg",
                                             "fnsku":  "",
                                             "mergePurchaseCost":  "0.0",
                                             "purchaseCost":  "-6870.37",
                                             "headTripCost":  "0.0",
                                             "headTripShare":  "false",
                                             "fbmShipCost":  "0.0",
                                             "asinUrl":  "https://www.amazon.co.jp/dp/B0GL2BF1YZ",
                                             "iossNumber":  null,
                                             "itemPrincipalAmountOri":  "22727.0",
                                             "itemTaxAmount":  "0.0",
                                             "promotionIds":  "",
                                             "fbaPerUnitFulfillmentFee":  "0.0",
                                             "commission":  "0.0",
                                             "amazonBackToArticle":  "25000.0",
                                             "withheldTaxAmount":  "0.0",
                                             "giftWrapTaxAmount":  "0.0",
                                             "shippingTaxAmount":  "0.0",
                                             "giftWrapAmount":  "0.0",
                                             "shippingCharge":  "0.0",
                                             "promotionDiscountAmount":  0.0,
                                             "otherAmount":  "0.0"
                                         }
                                     ],
                 "productAmount":  "25000.0",
                 "productAmountOri":  "22727.0",
                 "refundPrice":  "0.0",
                 "fbaPerUnitFulfillmentFee":  "0.0",
                 "commission":  "0.0",
                 "otherAmount":  "0.0",
                 "purchaseCost":  "-6870.37",
                 "headTripCost":  "0.0",
                 "headTripShare":  "false",
                 "fbmShipCost":  "0.0",
                 "orderProfit":  "17879.63",
                 "saleProfitRate":  "71.52",
                 "isReturnOrder":  "0",
                 "refundDate":  null,
                 "purchaseDate":  "2026-04-08 10:11:15",
                 "lastUpdateDate":  "2026-04-08 10:13:57",
                 "isReplacementOrder":  "0",
                 "isBusinessOrder":  "0",
                 "replacedOrderId":  null,
                 "fbmCostOrigin":  "0.0",
                 "fbmCost":  "0.0",
                 "totalCost":  "0.0",
                 "totalRevenue":  "0.0",
                 "fulfillmentChannel":  "MFN",
                 "fulfillmentComment":  null,
                 "receivedDate":  null,
                 "shippingCharge":  "0.0",
                 "promotionDiscount":  "0.0",
                 "taxAmount":  "2273.0",
                 "productTaxAmount":  "2273.0",
                 "amazonBackToArticle":  "24750.0",
                 "withheldTaxAmount":  "0.0",
                 "giftWrapAmount":  "0.0",
                 "newTaxAmount":  "2273.0",
                 "newOtherAmount":  "0.0",
                 "giftWrapTaxAmount":  "0.0",
                 "shippingTaxAmount":  "0.0",
                 "promotionFlag":  "false",
                 "taxNumber":  "",
                 "iossNumber":  null,
                 "otherDetails":  null,
                 "paymentExecutionDetail":  "[\"Standard\"]",
                 "isBudget":  null,
                 "isExpire":  "false",
                 "orderFlag":  "0",
                 "numberOfItemsUnshipped":  "1",
                 "fbmCostType":  "0",
                 "isHistory":  "0",
                 "isBuyerRequestedCancel":  "0",
                 "refundStatus":  "0",
                 "orderReviewStatus":  "未请求",
                 "orderPackageList":  null
             },
    "ts":  1775613904979,
    "requestId":  "fc8c8106-81b9-4302-92e5-98f34cf5bee0"
}
```
