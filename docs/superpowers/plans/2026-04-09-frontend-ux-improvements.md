# Frontend UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve frontend UX with table tooltips, column sorting, country dropdown, cleaner text, and cron preset selector.

**Architecture:** Pure frontend changes across 18 Vue files and 1 TS config. No backend changes. Each task is independent and can be committed separately.

**Tech Stack:** Vue 3.5, Element Plus 2.9, TypeScript 5.7, SCSS

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `frontend/src/views/WarehouseView.vue` | Tooltip, sorting, country dropdown, remove description |
| Modify | `frontend/src/views/ShopView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/SuggestionListView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/SkuConfigView.vue` | Tooltip, sorting |
| Modify | `frontend/src/views/ApiMonitorView.vue` | Tooltip, sorting |
| Modify | `frontend/src/views/SyncManagementView.vue` | Tooltip, sorting |
| Modify | `frontend/src/views/ZipcodeRuleView.vue` | Tooltip, sorting, remove hint |
| Modify | `frontend/src/views/HistoryView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/OverstockView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/data/DataProductsView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/data/DataInventoryView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/data/DataOrdersView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/data/DataOutRecordsView.vue` | Tooltip, sorting, remove description |
| Modify | `frontend/src/views/SuggestionDetailView.vue` | Tooltip, sorting |
| Modify | `frontend/src/views/ReplenishmentRunView.vue` | Remove description (no table) |
| Modify | `frontend/src/views/GlobalConfigView.vue` | Remove hints, cron preset dropdown |
| Modify | `frontend/src/views/sync/SyncAutoView.vue` | Remove description, remove card descriptions |
| Modify | `frontend/src/views/sync/SyncManualView.vue` | Remove description, remove card descriptions |
| Modify | `frontend/src/config/sync.ts` | Remove description fields from definitions |

---

### Task 1: Add `show-overflow-tooltip` to all table columns

Add the `show-overflow-tooltip` attribute to every `el-table-column` in all 13 table views. Remove any existing `:title` attributes that serve the same purpose.

**Files:**
- Modify: `frontend/src/views/WarehouseView.vue:11,19-21`
- Modify: `frontend/src/views/ShopView.vue:15,21-23,30`
- Modify: `frontend/src/views/SuggestionListView.vue:39-40,51-52,59,64,71`
- Modify: `frontend/src/views/SkuConfigView.vue:21,26,31`
- Modify: `frontend/src/views/ApiMonitorView.vue:47,52-55,58,61,69,72,75-78,81`
- Modify: `frontend/src/views/SyncManagementView.vue:56,61,66,71,79,130,133,136-139,144`
- Modify: `frontend/src/views/ZipcodeRuleView.vue:17-21,26-27,32`
- Modify: `frontend/src/views/HistoryView.vue:40-42,46-47,54-57,62`
- Modify: `frontend/src/views/OverstockView.vue:16,22-23,28-29,34,40`
- Modify: `frontend/src/views/data/DataProductsView.vue:31-33,38,46-50,56`
- Modify: `frontend/src/views/data/DataInventoryView.vue:33-34,39,47,53,58-59`
- Modify: `frontend/src/views/data/DataOrdersView.vue:49,54,59,64,69,75,78,84,89,125,128-132`
- Modify: `frontend/src/views/data/DataOutRecordsView.vue:36,41-42,50-52,60,66,69,74,80`
- Modify: `frontend/src/views/SuggestionDetailView.vue:45-47,54,71-72`

- [ ] **Step 1: WarehouseView — add show-overflow-tooltip**

In `frontend/src/views/WarehouseView.vue`, add `show-overflow-tooltip` to each `el-table-column`:

```vue
<!-- Line 11: has custom template, add attribute -->
<el-table-column label="仓库名称" prop="name" min-width="220" show-overflow-tooltip>

<!-- Line 19: simple prop column -->
<el-table-column label="仓库 ID" prop="id" width="140" show-overflow-tooltip />

<!-- Line 20 -->
<el-table-column label="类型" prop="type" width="100" align="center" show-overflow-tooltip />

<!-- Line 21: has custom template -->
<el-table-column label="赛狐 replenishSite" width="180" show-overflow-tooltip>

<!-- Line 26: has custom template (country input) -->
<el-table-column label="所属国家" width="220" show-overflow-tooltip>
```

- [ ] **Step 2: ShopView — add show-overflow-tooltip**

In `frontend/src/views/ShopView.vue`:

```vue
<!-- Line 15 -->
<el-table-column label="店铺" min-width="220" show-overflow-tooltip>

<!-- Line 21 -->
<el-table-column label="站点" prop="marketplace_id" width="160" show-overflow-tooltip />

<!-- Line 22 -->
<el-table-column label="区域" prop="region" width="120" show-overflow-tooltip />

<!-- Line 23 -->
<el-table-column label="授权状态" width="140" show-overflow-tooltip>

<!-- Line 30 -->
<el-table-column label="参与同步" width="120" align="center" show-overflow-tooltip>
```

- [ ] **Step 3: SuggestionListView — add show-overflow-tooltip**

In `frontend/src/views/SuggestionListView.vue`:

```vue
<!-- Line 39: selection column — skip tooltip (no text) -->
<!-- Line 40 -->
<el-table-column label="商品信息" min-width="320" show-overflow-tooltip>

<!-- Line 51 -->
<el-table-column label="总采购量" prop="total_qty" width="120" align="right" show-overflow-tooltip />

<!-- Line 52 -->
<el-table-column label="国家分布" min-width="220" show-overflow-tooltip>

<!-- Line 59 -->
<el-table-column label="最早采购日" width="140" show-overflow-tooltip>

<!-- Line 64 -->
<el-table-column label="推送状态" width="120" show-overflow-tooltip>

<!-- Line 71 -->
<el-table-column label="操作" width="100" align="center" show-overflow-tooltip>
```

- [ ] **Step 4: SkuConfigView — add show-overflow-tooltip**

In `frontend/src/views/SkuConfigView.vue`:

```vue
<!-- Line 21 -->
<el-table-column label="SKU" min-width="280" show-overflow-tooltip>

<!-- Line 26 -->
<el-table-column label="启用" width="100" align="center" show-overflow-tooltip>

<!-- Line 31 -->
<el-table-column label="覆盖提前期（天）" width="200" show-overflow-tooltip>
```

- [ ] **Step 5: ApiMonitorView — add show-overflow-tooltip**

In `frontend/src/views/ApiMonitorView.vue`, add `show-overflow-tooltip` to all columns in both tables (endpoint aggregation and recent calls). Remove any existing `:title` attributes:

```vue
<!-- Endpoint aggregation table -->
<!-- Line 47 -->
<el-table-column label="接口名称" min-width="220" show-overflow-tooltip>
<!-- Line 52 -->
<el-table-column label="总调用数" prop="total_calls" width="110" align="right" show-overflow-tooltip />
<!-- Line 53 -->
<el-table-column label="成功数" prop="success_count" width="100" align="right" show-overflow-tooltip />
<!-- Line 54 -->
<el-table-column label="失败数" prop="failed_count" width="100" align="right" show-overflow-tooltip />
<!-- Line 55 -->
<el-table-column label="成功率" width="120" align="right" show-overflow-tooltip>
<!-- Line 58 -->
<el-table-column label="最近调用时间" min-width="160" show-overflow-tooltip>
<!-- Line 61 -->
<el-table-column label="最近错误" min-width="260" show-overflow-tooltip>

<!-- Recent calls table -->
<!-- Line 69 -->
<el-table-column label="调用时间" min-width="160" show-overflow-tooltip>
<!-- Line 72 -->
<el-table-column label="接口名称" min-width="220" show-overflow-tooltip>
<!-- Line 75 -->
<el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" show-overflow-tooltip />
<!-- Line 76 -->
<el-table-column label="HTTP 状态" prop="http_status" width="100" align="center" show-overflow-tooltip />
<!-- Line 77 -->
<el-table-column label="赛狐返回码" prop="saihu_code" width="120" align="center" show-overflow-tooltip />
<!-- Line 78 -->
<el-table-column label="错误信息" min-width="260" show-overflow-tooltip>
<!-- Line 81 -->
<el-table-column label="操作" width="100" align="center" show-overflow-tooltip>
```

If any column has `:title="row.endpoint"` or similar, remove that `:title` attribute.

- [ ] **Step 6: SyncManagementView — add show-overflow-tooltip**

In `frontend/src/views/SyncManagementView.vue`, add `show-overflow-tooltip` to all columns in both tables (sync state table and recent calls table):

```vue
<!-- Sync state table -->
<!-- Line 56 -->
<el-table-column label="job_name" prop="job_name" min-width="200" show-overflow-tooltip>
<!-- Line 61 -->
<el-table-column label="最近运行" width="180" show-overflow-tooltip>
<!-- Line 66 -->
<el-table-column label="最近成功" width="180" show-overflow-tooltip>
<!-- Line 71 -->
<el-table-column label="状态" width="120" show-overflow-tooltip>
<!-- Line 79 -->
<el-table-column label="错误信息" min-width="240" show-overflow-tooltip>

<!-- Recent calls table -->
<!-- Line 130 -->
<el-table-column label="时间" width="170" show-overflow-tooltip>
<!-- Line 133 -->
<el-table-column label="接口" min-width="320" show-overflow-tooltip>
<!-- Line 136 -->
<el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" show-overflow-tooltip />
<!-- Line 137 -->
<el-table-column label="HTTP" prop="http_status" width="80" align="center" show-overflow-tooltip />
<!-- Line 138 -->
<el-table-column label="saihu code" prop="saihu_code" width="110" align="center" show-overflow-tooltip />
<!-- Line 139 -->
<el-table-column label="错误信息" min-width="180" show-overflow-tooltip>
<!-- Line 144 -->
<el-table-column label="操作" width="90" align="center" show-overflow-tooltip>
```

- [ ] **Step 7: ZipcodeRuleView — add show-overflow-tooltip**

In `frontend/src/views/ZipcodeRuleView.vue`:

```vue
<!-- Line 17: already has sortable -->
<el-table-column label="优先级" prop="priority" width="80" sortable show-overflow-tooltip />
<!-- Line 18 -->
<el-table-column label="国家" prop="country" width="80" show-overflow-tooltip />
<!-- Line 19 -->
<el-table-column label="截取前 N 位" prop="prefix_length" width="120" show-overflow-tooltip />
<!-- Line 20 -->
<el-table-column label="值类型" prop="value_type" width="100" show-overflow-tooltip />
<!-- Line 21 -->
<el-table-column label="比较符" width="80" show-overflow-tooltip>
<!-- Line 26 -->
<el-table-column label="比较值" prop="compare_value" width="120" show-overflow-tooltip />
<!-- Line 27 -->
<el-table-column label="目标仓库" prop="warehouse_id" min-width="160" show-overflow-tooltip>
<!-- Line 32 -->
<el-table-column label="操作" width="160" align="center" show-overflow-tooltip>
```

- [ ] **Step 8: HistoryView — add show-overflow-tooltip**

In `frontend/src/views/HistoryView.vue`:

```vue
<!-- Line 40 -->
<el-table-column label="建议单 ID" prop="id" width="100" show-overflow-tooltip />
<!-- Line 41 -->
<el-table-column label="生成时间" width="180" show-overflow-tooltip>
<!-- Line 46 -->
<el-table-column label="触发方式" prop="triggered_by" width="140" show-overflow-tooltip />
<!-- Line 47 -->
<el-table-column label="状态" width="120" show-overflow-tooltip>
<!-- Line 54 -->
<el-table-column label="条目数" prop="total_items" width="100" align="right" show-overflow-tooltip />
<!-- Line 55 -->
<el-table-column label="已推送" prop="pushed_items" width="100" align="right" show-overflow-tooltip />
<!-- Line 56 -->
<el-table-column label="失败数" prop="failed_items" width="100" align="right" show-overflow-tooltip />
<!-- Line 57 -->
<el-table-column label="推送成功率" width="120" align="right" show-overflow-tooltip>
<!-- Line 62 -->
<el-table-column label="操作" width="100" align="center" show-overflow-tooltip>
```

- [ ] **Step 9: OverstockView — add show-overflow-tooltip**

In `frontend/src/views/OverstockView.vue`:

```vue
<!-- Line 16 -->
<el-table-column label="SKU" min-width="280" show-overflow-tooltip>
<!-- Line 22 -->
<el-table-column label="国家" prop="country" width="100" show-overflow-tooltip />
<!-- Line 23 -->
<el-table-column label="仓库" min-width="180" show-overflow-tooltip>
<!-- Line 28 -->
<el-table-column label="当前库存" prop="current_stock" width="120" align="right" show-overflow-tooltip />
<!-- Line 29 -->
<el-table-column label="最近销售日期" width="160" show-overflow-tooltip>
<!-- Line 34 -->
<el-table-column label="处理状态" width="160" show-overflow-tooltip>
<!-- Line 40 -->
<el-table-column label="操作" width="120" align="center" show-overflow-tooltip>
```

- [ ] **Step 10: DataProductsView — add show-overflow-tooltip**

In `frontend/src/views/data/DataProductsView.vue`:

```vue
<!-- Line 31 -->
<el-table-column label="SKU" prop="commoditySku" min-width="180" show-overflow-tooltip />
<!-- Line 32 -->
<el-table-column label="商品 ID" prop="commodityId" width="120" show-overflow-tooltip />
<!-- Line 33 -->
<el-table-column label="商品名称" min-width="200" show-overflow-tooltip>
<!-- Line 38 -->
<el-table-column label="店铺/站点" width="180" show-overflow-tooltip>
<!-- Line 46 -->
<el-table-column label="Seller SKU" prop="sellerSku" width="160" show-overflow-tooltip />
<!-- Line 47 -->
<el-table-column label="7天销量" prop="day7SaleNum" width="90" align="right" show-overflow-tooltip />
<!-- Line 48 -->
<el-table-column label="14天销量" prop="day14SaleNum" width="90" align="right" show-overflow-tooltip />
<!-- Line 49 -->
<el-table-column label="30天销量" prop="day30SaleNum" width="90" align="right" show-overflow-tooltip />
<!-- Line 50 -->
<el-table-column label="匹配状态" width="100" show-overflow-tooltip>
<!-- Line 56 -->
<el-table-column label="最后同步" width="160" show-overflow-tooltip>
```

- [ ] **Step 11: DataInventoryView — add show-overflow-tooltip**

In `frontend/src/views/data/DataInventoryView.vue`:

```vue
<!-- Line 33 -->
<el-table-column label="SKU" prop="commoditySku" min-width="180" show-overflow-tooltip />
<!-- Line 34 -->
<el-table-column label="商品名称" min-width="200" show-overflow-tooltip>
<!-- Line 39 -->
<el-table-column label="仓库" min-width="180" show-overflow-tooltip>
<!-- Line 47 -->
<el-table-column label="国家" prop="country" width="80" align="center" show-overflow-tooltip>
<!-- Line 53 -->
<el-table-column label="可用库存" prop="stockAvailable" width="140" align="right" show-overflow-tooltip>
<!-- Line 58 -->
<el-table-column label="占用库存" prop="stockOccupy" width="120" align="right" show-overflow-tooltip />
<!-- Line 59 -->
<el-table-column label="更新时间" width="160" show-overflow-tooltip>
```

- [ ] **Step 12: DataOrdersView — add show-overflow-tooltip**

In `frontend/src/views/data/DataOrdersView.vue`, add to both main table and dialog detail table:

```vue
<!-- Main table -->
<!-- Line 49 -->
<el-table-column label="订单号" prop="amazonOrderId" width="220" show-overflow-tooltip>
<!-- Line 54 -->
<el-table-column label="店铺" prop="shopId" width="100" show-overflow-tooltip>
<!-- Line 59 -->
<el-table-column label="国家" width="80" align="center" show-overflow-tooltip>
<!-- Line 64 -->
<el-table-column label="状态" width="140" show-overflow-tooltip>
<!-- Line 69 -->
<el-table-column label="金额" width="120" align="right" show-overflow-tooltip>
<!-- Line 75 -->
<el-table-column label="明细数" width="80" align="right" show-overflow-tooltip>
<!-- Line 78 -->
<el-table-column label="详情状态" width="100" align="center" show-overflow-tooltip>
<!-- Line 84 -->
<el-table-column label="下单时间" width="160" show-overflow-tooltip>
<!-- Line 89 -->
<el-table-column label="操作" width="100" align="center" show-overflow-tooltip>

<!-- Dialog detail table -->
<!-- Line 125 -->
<el-table-column label="orderItemId" prop="orderItemId" width="160" show-overflow-tooltip>
<!-- Line 128 -->
<el-table-column label="commoditySku" prop="commoditySku" min-width="160" show-overflow-tooltip />
<!-- Line 129 -->
<el-table-column label="sellerSku" prop="sellerSku" width="140" show-overflow-tooltip />
<!-- Line 130 -->
<el-table-column label="ordered" prop="quantityOrdered" width="80" align="right" show-overflow-tooltip />
<!-- Line 131 -->
<el-table-column label="shipped" prop="quantityShipped" width="80" align="right" show-overflow-tooltip />
<!-- Line 132 -->
<el-table-column label="refund" prop="refundNum" width="80" align="right" show-overflow-tooltip />
```

- [ ] **Step 13: DataOutRecordsView — add show-overflow-tooltip**

In `frontend/src/views/data/DataOutRecordsView.vue`, add to both main table and expand sub-table:

```vue
<!-- Main table (skip type="expand" column at line 36) -->
<!-- Line 50 -->
<el-table-column label="出库单号" prop="outWarehouseNo" min-width="160" show-overflow-tooltip />
<!-- Line 51 -->
<el-table-column label="赛狐出库 ID" prop="saihuOutRecordId" width="160" show-overflow-tooltip />
<!-- Line 52 -->
<el-table-column label="目标仓" min-width="200" show-overflow-tooltip>
<!-- Line 60 -->
<el-table-column label="目标国家" width="90" align="center" show-overflow-tooltip>
<!-- Line 66 -->
<el-table-column label="明细数" width="90" align="right" show-overflow-tooltip>
<!-- Line 69 -->
<el-table-column label="观测总数" width="100" align="right" show-overflow-tooltip>
<!-- Line 74 -->
<el-table-column label="状态" width="100" show-overflow-tooltip>
<!-- Line 80 -->
<el-table-column label="最后同步" width="160" show-overflow-tooltip>

<!-- Expand sub-table -->
<!-- Line 41 -->
<el-table-column label="commoditySku" prop="commoditySku" show-overflow-tooltip />
<!-- Line 42 -->
<el-table-column label="goods（观测值）" prop="goods" width="160" align="right" show-overflow-tooltip />
```

- [ ] **Step 14: SuggestionDetailView — add show-overflow-tooltip**

In `frontend/src/views/SuggestionDetailView.vue`:

```vue
<!-- Line 45 -->
<el-table-column prop="country" label="国家" width="80" show-overflow-tooltip />
<!-- Line 46 -->
<el-table-column prop="qty" label="国家总量" width="100" show-overflow-tooltip />
<!-- Line 47 -->
<el-table-column label="各仓明细" show-overflow-tooltip>
<!-- Line 54 -->
<el-table-column label="拆分依据" min-width="220" show-overflow-tooltip>
<!-- Line 71 -->
<el-table-column prop="t_purchase" label="采购时间" width="120" show-overflow-tooltip />
<!-- Line 72 -->
<el-table-column prop="t_ship" label="发货时间" width="120" show-overflow-tooltip />
```

- [ ] **Step 15: Verify tooltip changes build correctly**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: No new errors.

- [ ] **Step 16: Commit tooltip changes**

```bash
git add frontend/src/views/
git commit -m "feat(ui): add show-overflow-tooltip to all table columns"
```

---

### Task 2: Add `sortable` to appropriate table columns

Add `sortable` attribute to non-long-text, non-action columns. Skip: SkuCard component columns, long text columns (商品名称, 错误信息, endpoint URLs, 拆分依据, 各仓明细), action/operation columns, selection columns, expand columns, and columns with interactive widgets (switch, input).

**Files:** Same 13 table view files as Task 1.

- [ ] **Step 1: WarehouseView — add sortable**

In `frontend/src/views/WarehouseView.vue`:

```vue
<!-- Line 11: 仓库名称 — short-ish text, add sortable -->
<el-table-column label="仓库名称" prop="name" min-width="220" show-overflow-tooltip sortable>

<!-- Line 19: 仓库 ID -->
<el-table-column label="仓库 ID" prop="id" width="140" show-overflow-tooltip sortable />

<!-- Line 20: 类型 -->
<el-table-column label="类型" prop="type" width="100" align="center" show-overflow-tooltip sortable />

<!-- Line 21: 赛狐 replenishSite — short code, add sortable -->
<el-table-column label="赛狐 replenishSite" width="180" show-overflow-tooltip sortable>

<!-- Line 26: 所属国家 — has input widget, skip sortable -->
```

- [ ] **Step 2: ShopView — add sortable**

In `frontend/src/views/ShopView.vue`:

```vue
<!-- Line 15: 店铺 — short name, sortable -->
<el-table-column label="店铺" min-width="220" show-overflow-tooltip sortable>

<!-- Line 21: 站点 -->
<el-table-column label="站点" prop="marketplace_id" width="160" show-overflow-tooltip sortable />

<!-- Line 22: 区域 -->
<el-table-column label="区域" prop="region" width="120" show-overflow-tooltip sortable />

<!-- Line 23: 授权状态 — short tag -->
<el-table-column label="授权状态" width="140" show-overflow-tooltip sortable>

<!-- Line 30: 参与同步 — has switch widget, skip sortable -->
```

- [ ] **Step 3: SuggestionListView — add sortable**

In `frontend/src/views/SuggestionListView.vue`:

```vue
<!-- Line 39: selection — skip -->
<!-- Line 40: 商品信息 — SkuCard component, skip -->
<!-- Line 51: 总采购量 — numeric -->
<el-table-column label="总采购量" prop="total_qty" width="120" align="right" show-overflow-tooltip sortable />

<!-- Line 52: 国家分布 — complex chips, skip -->
<!-- Line 59: 最早采购日 — date -->
<el-table-column label="最早采购日" width="140" show-overflow-tooltip sortable>

<!-- Line 64: 推送状态 — short tag -->
<el-table-column label="推送状态" width="120" show-overflow-tooltip sortable>

<!-- Line 71: 操作 — skip -->
```

- [ ] **Step 4: SkuConfigView — add sortable**

In `frontend/src/views/SkuConfigView.vue`:

```vue
<!-- Line 21: SKU — SkuCard-like display, skip -->
<!-- Line 26: 启用 — has switch, skip -->
<!-- Line 31: 覆盖提前期 — has input, skip -->
```

No columns get sortable in this view.

- [ ] **Step 5: ApiMonitorView — add sortable**

In `frontend/src/views/ApiMonitorView.vue`:

```vue
<!-- Endpoint aggregation table -->
<!-- Line 47: 接口名称 — short name, sortable -->
<el-table-column label="接口名称" min-width="220" show-overflow-tooltip sortable>
<!-- Line 52: 总调用数 — numeric -->
<el-table-column label="总调用数" prop="total_calls" width="110" align="right" show-overflow-tooltip sortable />
<!-- Line 53: 成功数 — numeric -->
<el-table-column label="成功数" prop="success_count" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 54: 失败数 — numeric -->
<el-table-column label="失败数" prop="failed_count" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 55: 成功率 — numeric -->
<el-table-column label="成功率" width="120" align="right" show-overflow-tooltip sortable>
<!-- Line 58: 最近调用时间 — date -->
<el-table-column label="最近调用时间" min-width="160" show-overflow-tooltip sortable>
<!-- Line 61: 最近错误 — long text, skip -->

<!-- Recent calls table -->
<!-- Line 69: 调用时间 — date -->
<el-table-column label="调用时间" min-width="160" show-overflow-tooltip sortable>
<!-- Line 72: 接口名称 — short name -->
<el-table-column label="接口名称" min-width="220" show-overflow-tooltip sortable>
<!-- Line 75: 耗时 — numeric -->
<el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 76: HTTP 状态 — short code -->
<el-table-column label="HTTP 状态" prop="http_status" width="100" align="center" show-overflow-tooltip sortable />
<!-- Line 77: 赛狐返回码 — short code -->
<el-table-column label="赛狐返回码" prop="saihu_code" width="120" align="center" show-overflow-tooltip sortable />
<!-- Line 78: 错误信息 — long text, skip -->
<!-- Line 81: 操作 — skip -->
```

- [ ] **Step 6: SyncManagementView — add sortable**

In `frontend/src/views/SyncManagementView.vue`:

```vue
<!-- Sync state table -->
<!-- Line 56: job_name — short code -->
<el-table-column label="job_name" prop="job_name" min-width="200" show-overflow-tooltip sortable>
<!-- Line 61: 最近运行 — date -->
<el-table-column label="最近运行" width="180" show-overflow-tooltip sortable>
<!-- Line 66: 最近成功 — date -->
<el-table-column label="最近成功" width="180" show-overflow-tooltip sortable>
<!-- Line 71: 状态 — short tag -->
<el-table-column label="状态" width="120" show-overflow-tooltip sortable>
<!-- Line 79: 错误信息 — long text, skip -->

<!-- Recent calls table -->
<!-- Line 130: 时间 — date -->
<el-table-column label="时间" width="170" show-overflow-tooltip sortable>
<!-- Line 133: 接口 — long URL, skip -->
<!-- Line 136: 耗时 — numeric -->
<el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 137: HTTP — short code -->
<el-table-column label="HTTP" prop="http_status" width="80" align="center" show-overflow-tooltip sortable />
<!-- Line 138: saihu code — short code -->
<el-table-column label="saihu code" prop="saihu_code" width="110" align="center" show-overflow-tooltip sortable />
<!-- Line 139: 错误信息 — long text, skip -->
<!-- Line 144: 操作 — skip -->
```

- [ ] **Step 7: ZipcodeRuleView — add sortable**

In `frontend/src/views/ZipcodeRuleView.vue` (line 17 already has `sortable`):

```vue
<!-- Line 17: already has sortable, no change needed -->
<!-- Line 18: 国家 -->
<el-table-column label="国家" prop="country" width="80" show-overflow-tooltip sortable />
<!-- Line 19: 截取前 N 位 — numeric -->
<el-table-column label="截取前 N 位" prop="prefix_length" width="120" show-overflow-tooltip sortable />
<!-- Line 20: 值类型 — short code -->
<el-table-column label="值类型" prop="value_type" width="100" show-overflow-tooltip sortable />
<!-- Line 21: 比较符 — short code -->
<el-table-column label="比较符" width="80" show-overflow-tooltip sortable>
<!-- Line 26: 比较值 — short -->
<el-table-column label="比较值" prop="compare_value" width="120" show-overflow-tooltip sortable />
<!-- Line 27: 目标仓库 — short name -->
<el-table-column label="目标仓库" prop="warehouse_id" min-width="160" show-overflow-tooltip sortable>
<!-- Line 32: 操作 — skip -->
```

- [ ] **Step 8: HistoryView — add sortable**

In `frontend/src/views/HistoryView.vue`:

```vue
<!-- Line 40: 建议单 ID — numeric -->
<el-table-column label="建议单 ID" prop="id" width="100" show-overflow-tooltip sortable />
<!-- Line 41: 生成时间 — date -->
<el-table-column label="生成时间" width="180" show-overflow-tooltip sortable>
<!-- Line 46: 触发方式 — short code -->
<el-table-column label="触发方式" prop="triggered_by" width="140" show-overflow-tooltip sortable />
<!-- Line 47: 状态 — short tag -->
<el-table-column label="状态" width="120" show-overflow-tooltip sortable>
<!-- Line 54: 条目数 — numeric -->
<el-table-column label="条目数" prop="total_items" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 55: 已推送 — numeric -->
<el-table-column label="已推送" prop="pushed_items" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 56: 失败数 — numeric -->
<el-table-column label="失败数" prop="failed_items" width="100" align="right" show-overflow-tooltip sortable />
<!-- Line 57: 推送成功率 — numeric -->
<el-table-column label="推送成功率" width="120" align="right" show-overflow-tooltip sortable>
<!-- Line 62: 操作 — skip -->
```

- [ ] **Step 9: OverstockView — add sortable**

In `frontend/src/views/OverstockView.vue`:

```vue
<!-- Line 16: SKU — SkuCard, skip -->
<!-- Line 22: 国家 — short code -->
<el-table-column label="国家" prop="country" width="100" show-overflow-tooltip sortable />
<!-- Line 23: 仓库 — short name -->
<el-table-column label="仓库" min-width="180" show-overflow-tooltip sortable>
<!-- Line 28: 当前库存 — numeric -->
<el-table-column label="当前库存" prop="current_stock" width="120" align="right" show-overflow-tooltip sortable />
<!-- Line 29: 最近销售日期 — date -->
<el-table-column label="最近销售日期" width="160" show-overflow-tooltip sortable>
<!-- Line 34: 处理状态 — short tag -->
<el-table-column label="处理状态" width="160" show-overflow-tooltip sortable>
<!-- Line 40: 操作 — skip -->
```

- [ ] **Step 10: DataProductsView — add sortable**

In `frontend/src/views/data/DataProductsView.vue`:

```vue
<!-- Line 31: SKU — short code -->
<el-table-column label="SKU" prop="commoditySku" min-width="180" show-overflow-tooltip sortable />
<!-- Line 32: 商品 ID — short code -->
<el-table-column label="商品 ID" prop="commodityId" width="120" show-overflow-tooltip sortable />
<!-- Line 33: 商品名称 — long text, skip -->
<!-- Line 38: 店铺/站点 — short name -->
<el-table-column label="店铺/站点" width="180" show-overflow-tooltip sortable>
<!-- Line 46: Seller SKU — short code -->
<el-table-column label="Seller SKU" prop="sellerSku" width="160" show-overflow-tooltip sortable />
<!-- Line 47: 7天销量 — numeric -->
<el-table-column label="7天销量" prop="day7SaleNum" width="90" align="right" show-overflow-tooltip sortable />
<!-- Line 48: 14天销量 — numeric -->
<el-table-column label="14天销量" prop="day14SaleNum" width="90" align="right" show-overflow-tooltip sortable />
<!-- Line 49: 30天销量 — numeric -->
<el-table-column label="30天销量" prop="day30SaleNum" width="90" align="right" show-overflow-tooltip sortable />
<!-- Line 50: 匹配状态 — short tag -->
<el-table-column label="匹配状态" width="100" show-overflow-tooltip sortable>
<!-- Line 56: 最后同步 — date -->
<el-table-column label="最后同步" width="160" show-overflow-tooltip sortable>
```

- [ ] **Step 11: DataInventoryView — add sortable**

In `frontend/src/views/data/DataInventoryView.vue`:

```vue
<!-- Line 33: SKU — short code -->
<el-table-column label="SKU" prop="commoditySku" min-width="180" show-overflow-tooltip sortable />
<!-- Line 34: 商品名称 — long text, skip -->
<!-- Line 39: 仓库 — short name -->
<el-table-column label="仓库" min-width="180" show-overflow-tooltip sortable>
<!-- Line 47: 国家 — short code -->
<el-table-column label="国家" prop="country" width="80" align="center" show-overflow-tooltip sortable>
<!-- Line 53: 可用库存 — numeric -->
<el-table-column label="可用库存" prop="stockAvailable" width="140" align="right" show-overflow-tooltip sortable>
<!-- Line 58: 占用库存 — numeric -->
<el-table-column label="占用库存" prop="stockOccupy" width="120" align="right" show-overflow-tooltip sortable />
<!-- Line 59: 更新时间 — date -->
<el-table-column label="更新时间" width="160" show-overflow-tooltip sortable>
```

- [ ] **Step 12: DataOrdersView — add sortable**

In `frontend/src/views/data/DataOrdersView.vue`:

```vue
<!-- Main table -->
<!-- Line 49: 订单号 — short code -->
<el-table-column label="订单号" prop="amazonOrderId" width="220" show-overflow-tooltip sortable>
<!-- Line 54: 店铺 — short code -->
<el-table-column label="店铺" prop="shopId" width="100" show-overflow-tooltip sortable>
<!-- Line 59: 国家 — short code -->
<el-table-column label="国家" width="80" align="center" show-overflow-tooltip sortable>
<!-- Line 64: 状态 — short tag -->
<el-table-column label="状态" width="140" show-overflow-tooltip sortable>
<!-- Line 69: 金额 — numeric -->
<el-table-column label="金额" width="120" align="right" show-overflow-tooltip sortable>
<!-- Line 75: 明细数 — numeric -->
<el-table-column label="明细数" width="80" align="right" show-overflow-tooltip sortable>
<!-- Line 78: 详情状态 — short tag -->
<el-table-column label="详情状态" width="100" align="center" show-overflow-tooltip sortable>
<!-- Line 84: 下单时间 — date -->
<el-table-column label="下单时间" width="160" show-overflow-tooltip sortable>
<!-- Line 89: 操作 — skip -->

<!-- Dialog detail table — small sub-table, add sortable to code/numeric columns -->
<!-- Line 125: orderItemId — skip (long ID) -->
<!-- Line 128: commoditySku — short code -->
<el-table-column label="commoditySku" prop="commoditySku" min-width="160" show-overflow-tooltip sortable />
<!-- Line 129: sellerSku — short code -->
<el-table-column label="sellerSku" prop="sellerSku" width="140" show-overflow-tooltip sortable />
<!-- Line 130: ordered — numeric -->
<el-table-column label="ordered" prop="quantityOrdered" width="80" align="right" show-overflow-tooltip sortable />
<!-- Line 131: shipped — numeric -->
<el-table-column label="shipped" prop="quantityShipped" width="80" align="right" show-overflow-tooltip sortable />
<!-- Line 132: refund — numeric -->
<el-table-column label="refund" prop="refundNum" width="80" align="right" show-overflow-tooltip sortable />
```

- [ ] **Step 13: DataOutRecordsView — add sortable**

In `frontend/src/views/data/DataOutRecordsView.vue`:

```vue
<!-- Main table (skip expand column) -->
<!-- Line 50: 出库单号 — short code -->
<el-table-column label="出库单号" prop="outWarehouseNo" min-width="160" show-overflow-tooltip sortable />
<!-- Line 51: 赛狐出库 ID — short code -->
<el-table-column label="赛狐出库 ID" prop="saihuOutRecordId" width="160" show-overflow-tooltip sortable />
<!-- Line 52: 目标仓 — short name -->
<el-table-column label="目标仓" min-width="200" show-overflow-tooltip sortable>
<!-- Line 60: 目标国家 — short code -->
<el-table-column label="目标国家" width="90" align="center" show-overflow-tooltip sortable>
<!-- Line 66: 明细数 — numeric -->
<el-table-column label="明细数" width="90" align="right" show-overflow-tooltip sortable>
<!-- Line 69: 观测总数 — numeric -->
<el-table-column label="观测总数" width="100" align="right" show-overflow-tooltip sortable>
<!-- Line 74: 状态 — short tag -->
<el-table-column label="状态" width="100" show-overflow-tooltip sortable>
<!-- Line 80: 最后同步 — date -->
<el-table-column label="最后同步" width="160" show-overflow-tooltip sortable>

<!-- Sub-table -->
<!-- Line 41: commoditySku — short code -->
<el-table-column label="commoditySku" prop="commoditySku" show-overflow-tooltip sortable />
<!-- Line 42: goods — numeric -->
<el-table-column label="goods（观测值）" prop="goods" width="160" align="right" show-overflow-tooltip sortable />
```

- [ ] **Step 14: SuggestionDetailView — add sortable**

In `frontend/src/views/SuggestionDetailView.vue`:

```vue
<!-- Line 45: 国家 — short code -->
<el-table-column prop="country" label="国家" width="80" show-overflow-tooltip sortable />
<!-- Line 46: 国家总量 — numeric -->
<el-table-column prop="qty" label="国家总量" width="100" show-overflow-tooltip sortable />
<!-- Line 47: 各仓明细 — complex nested, skip -->
<!-- Line 54: 拆分依据 — long text, skip -->
<!-- Line 71: 采购时间 — date -->
<el-table-column prop="t_purchase" label="采购时间" width="120" show-overflow-tooltip sortable />
<!-- Line 72: 发货时间 — date -->
<el-table-column prop="t_ship" label="发货时间" width="120" show-overflow-tooltip sortable />
```

- [ ] **Step 15: Verify sorting changes build correctly**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: No new errors.

- [ ] **Step 16: Commit sorting changes**

```bash
git add frontend/src/views/
git commit -m "feat(ui): add column sorting to all table views"
```

---

### Task 3: Replace warehouse country text input with dropdown

**Files:**
- Modify: `frontend/src/views/WarehouseView.vue:26-37,74-79`

- [ ] **Step 1: Add countryOptions data and update template**

In `frontend/src/views/WarehouseView.vue`, replace the `el-input` (lines 28-35) with `el-select`:

Replace this template block:
```vue
          <el-input
            v-model="row.country"
            placeholder="ISO 两位码"
            maxlength="2"
            style="width: 140px"
            @blur="(e: Event) => save(row, (e.target as HTMLInputElement).value)"
            @keyup.enter="(e: Event) => save(row, (e.target as HTMLInputElement).value)"
          />
```

With:
```vue
          <el-select
            v-model="row.country"
            filterable
            placeholder="选择国家"
            style="width: 180px"
            @change="(val: string) => save(row, val)"
          >
            <el-option
              v-for="opt in countryOptions"
              :key="opt.code"
              :label="opt.label"
              :value="opt.code"
            />
          </el-select>
```

- [ ] **Step 2: Add countryOptions constant in script setup**

In the `<script setup>` section, add after the `pageSize` ref (after line 58):

```typescript
const countryOptions = [
  { code: 'US', label: 'US - 美国' },
  { code: 'CA', label: 'CA - 加拿大' },
  { code: 'MX', label: 'MX - 墨西哥' },
  { code: 'GB', label: 'GB - 英国' },
  { code: 'DE', label: 'DE - 德国' },
  { code: 'FR', label: 'FR - 法国' },
  { code: 'IT', label: 'IT - 意大利' },
  { code: 'ES', label: 'ES - 西班牙' },
  { code: 'IN', label: 'IN - 印度' },
  { code: 'JP', label: 'JP - 日本' },
  { code: 'AU', label: 'AU - 澳大利亚' },
  { code: 'AE', label: 'AE - 阿联酋' },
  { code: 'TR', label: 'TR - 土耳其' },
  { code: 'SG', label: 'SG - 新加坡' },
  { code: 'BR', label: 'BR - 巴西' },
  { code: 'NL', label: 'NL - 荷兰' },
  { code: 'SA', label: 'SA - 沙特阿拉伯' },
  { code: 'SE', label: 'SE - 瑞典' },
  { code: 'PL', label: 'PL - 波兰' },
  { code: 'BE', label: 'BE - 比利时' },
  { code: 'IE', label: 'IE - 爱尔兰' },
]
```

- [ ] **Step 3: Simplify the save function**

Replace the save function (lines 74-88) — remove the manual trim/uppercase/length validation since the dropdown constrains input:

```typescript
async function save(row: Warehouse, value: string): Promise<void> {
  if (!value || value === row.country) return
  try {
    await patchWarehouseCountry(row.id, value)
    row.country = value
    ElMessage.success(`${row.name} 已更新为 ${value}。`)
  } catch {
    ElMessage.error('更新失败。')
  }
}
```

- [ ] **Step 4: Verify build**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: No new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/WarehouseView.vue
git commit -m "feat(ui): replace warehouse country text input with searchable dropdown"
```

---

### Task 4: Remove all page descriptions and hints

**Files:**
- Modify: `frontend/src/views/WarehouseView.vue:4`
- Modify: `frontend/src/views/ShopView.vue:8`
- Modify: `frontend/src/views/SuggestionListView.vue:8`
- Modify: `frontend/src/views/HistoryView.vue:7`
- Modify: `frontend/src/views/OverstockView.vue:7`
- Modify: `frontend/src/views/data/DataProductsView.vue:7`
- Modify: `frontend/src/views/data/DataInventoryView.vue:7`
- Modify: `frontend/src/views/data/DataOrdersView.vue:7`
- Modify: `frontend/src/views/data/DataOutRecordsView.vue:7`
- Modify: `frontend/src/views/ReplenishmentRunView.vue:6,15-17,28,33`
- Modify: `frontend/src/views/GlobalConfigView.vue:10,14,18,25,29`
- Modify: `frontend/src/views/ZipcodeRuleView.vue:2,80`
- Modify: `frontend/src/views/sync/SyncAutoView.vue:3-7,12-14,26`
- Modify: `frontend/src/views/sync/SyncManualView.vue:6-8,24`
- Modify: `frontend/src/config/sync.ts`

- [ ] **Step 1: WarehouseView — remove description prop**

In `frontend/src/views/WarehouseView.vue`, remove the `description` prop from PageSectionCard:

Change line 2-5 from:
```vue
  <PageSectionCard
    title="仓库配置"
    description="维护仓库与国家映射。页面级表格统一支持分页。"
  >
```
To:
```vue
  <PageSectionCard title="仓库配置">
```

- [ ] **Step 2: ShopView — remove card-meta**

In `frontend/src/views/ShopView.vue`, delete line 8:
```vue
            <div class="card-meta">店铺状态统一显示为业务含义，不再直接暴露状态码。</div>
```

- [ ] **Step 3: SuggestionListView — remove card-meta**

In `frontend/src/views/SuggestionListView.vue`, delete line 8:
```vue
            <div class="card-meta">当前活动建议单条目列表，支持筛选、分页和批量推送。</div>
```

- [ ] **Step 4: HistoryView — remove card-meta**

In `frontend/src/views/HistoryView.vue`, delete line 7:
```vue
            <div class="card-meta">按时间、状态和 SKU 过滤历史建议单。</div>
```

- [ ] **Step 5: OverstockView — remove card-meta**

In `frontend/src/views/OverstockView.vue`, delete line 7:
```vue
            <div class="card-meta">支持分页查看积压 SKU，并记录是否已人工处理。</div>
```

- [ ] **Step 6: DataProductsView — remove card-meta**

In `frontend/src/views/data/DataProductsView.vue`, delete line 7:
```vue
          <span class="card-meta">product_listing，来自 /api/order/api/product/pageList.json</span>
```

- [ ] **Step 7: DataInventoryView — remove card-meta**

In `frontend/src/views/data/DataInventoryView.vue`, delete line 7:
```vue
          <span class="card-meta">inventory_snapshot_latest，来自 /api/warehouseManage/warehouseItemList.json</span>
```

- [ ] **Step 8: DataOrdersView — remove card-meta**

In `frontend/src/views/data/DataOrdersView.vue`, delete line 7:
```vue
          <span class="card-meta">order_header，来自 /api/order/pageList.json，支持查看同步后的订单详情。</span>
```

- [ ] **Step 9: DataOutRecordsView — remove card-meta**

In `frontend/src/views/data/DataOutRecordsView.vue`, delete line 7:
```vue
          <span class="card-meta">in_transit_record，来自 /api/warehouseInOut/outRecords.json，当前补货统一按 0 处理。</span>
```

- [ ] **Step 10: ReplenishmentRunView — remove descriptions**

In `frontend/src/views/ReplenishmentRunView.vue`:

Remove the `description` prop from DashboardPageHeader (line 6):
```vue
    <DashboardPageHeader
      eyebrow="Engine"
      title="补货触发"
    >
```
(Delete: `description="补货触发页只负责执行规则引擎，不再承载同步操作。建议先在数据同步中心确认关键同步完成，再执行补货建议生成。"`)

Remove `hint` props from DashboardStatCard elements (lines 15-22):
```vue
      <DashboardStatCard title="当前建议单" :value="suggestion ? `#${suggestion.id}` : '-'" />
      <DashboardStatCard title="建议状态" :value="statusMeta.label" />
      <DashboardStatCard title="建议条目数" :value="suggestion?.total_items ?? 0" />
      <DashboardStatCard
        title="已推送条目"
        :value="suggestion?.pushed_items ?? 0"
      />
```

Remove `description` prop from DashboardChartCard (line 28):
Change:
```vue
        description="按当前活动建议单聚合国家维度采购量。"
```
To: delete that line.

Remove `description` prop from DataTableCard (line 33):
Change:
```vue
      <DataTableCard title="当前建议摘要" description="执行引擎前可先确认当前建议单的基本情况。">
```
To:
```vue
      <DataTableCard title="当前建议摘要">
```

- [ ] **Step 11: GlobalConfigView — remove all hints**

In `frontend/src/views/GlobalConfigView.vue`, delete each `<span class="hint">...</span>` line:

- Line 10: `<span class="hint">BUFFER_DAYS — Step 4 公式</span>`
- Line 14: `<span class="hint">TARGET_DAYS — Step 3 / Step 6 公式</span>`
- Line 18: `<span class="hint">LEAD_TIME_DAYS — SKU 级 lead_time 缺省时使用</span>`
- Line 25: `<span class="hint">默认每天 08:00 北京时间</span>`
- Line 29: `<span class="hint">推送采购单时使用</span>`

Also remove the `.hint` CSS rule (lines 81-85) since no hints remain.

- [ ] **Step 12: ZipcodeRuleView — remove description and hint**

In `frontend/src/views/ZipcodeRuleView.vue`:

Remove description from PageSectionCard (line 2):
```vue
  <PageSectionCard title="邮编规则">
```
(Delete: `description="按国家筛选和维护邮编分仓规则。"`)

Delete hint at line 80:
```vue
          <span class="hint">数字越小越先匹配</span>
```

- [ ] **Step 13: SyncAutoView — remove descriptions**

In `frontend/src/views/sync/SyncAutoView.vue`:

Delete the el-alert (lines 3-7):
```vue
    <el-alert
      type="info"
      :closable="false"
      title="当前阶段先提供自动同步看板，展示建议频率和最近执行状态；若后端补齐调度控制接口，可在此页继续接入开关与计划编辑。"
    />
```

Delete the `<p>` description (lines 12-14):
```vue
        <p class="page-desc">
          自动同步页负责说明建议执行频率和最近运行结果，帮助判断哪些任务应纳入调度器统一托管。
        </p>
```

Delete line 26 (card description display):
```vue
          <div class="job-card__desc">{{ job.description }}</div>
```

Remove the `.page-desc` CSS rule (lines 95-98) and `.job-card__desc` from the CSS selector (line 123).

- [ ] **Step 14: SyncManualView — remove descriptions**

In `frontend/src/views/sync/SyncManualView.vue`:

Delete the `<p>` description (lines 6-8):
```vue
        <p class="page-desc">
          手动同步页只负责触发外部数据拉取，不包含规则引擎执行。全量同步会按既定顺序触发全部同步任务。
        </p>
```

Delete line 24 (card description display):
```vue
              <div class="sync-card__desc">{{ action.description }}</div>
```

Remove the `.page-desc` CSS rule (lines 137-140) and `.sync-card__desc` from the CSS selector (line 169).

- [ ] **Step 15: sync.ts — remove description fields**

In `frontend/src/config/sync.ts`, remove all `description` fields from the interfaces and data:

Update interfaces:
```typescript
export interface SyncActionDefinition {
  key: string
  jobName: string
  label: string
  url: string
}

export interface AutoSyncDefinition {
  jobName: string
  label: string
  cadence: string
}
```

Remove `description: '...'` lines from every entry in `manualSyncActions` (lines 21, 28, 35, 42, 49, 56, 63), `replenishmentAction` (line 71), and `autoSyncDefinitions` (lines 79, 85, 91, 97, 103, 109, 115).

- [ ] **Step 16: Verify build**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: No new errors.

- [ ] **Step 17: Commit**

```bash
git add frontend/src/views/ frontend/src/config/sync.ts
git commit -m "feat(ui): remove all page descriptions and field hints for cleaner interface"
```

---

### Task 5: Replace cron text input with preset dropdown + custom input

**Files:**
- Modify: `frontend/src/views/GlobalConfigView.vue:23-26,50-53`

- [ ] **Step 1: Add cron preset data and computed logic in script setup**

In `frontend/src/views/GlobalConfigView.vue`, add after the `saving` ref (after line 56):

```typescript
const cronPresets = [
  { label: '每天 06:00', value: '0 6 * * *' },
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每天 12:00', value: '0 12 * * *' },
  { label: '每天 20:00', value: '0 20 * * *' },
  { label: '每 12 小时', value: '0 */12 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '自定义', value: '__custom__' },
]

const selectedCronPreset = ref('__custom__')
const customCron = ref('')

function initCronState(): void {
  if (!form.value) return
  const match = cronPresets.find((p) => p.value === form.value!.calc_cron)
  if (match && match.value !== '__custom__') {
    selectedCronPreset.value = match.value
  } else {
    selectedCronPreset.value = '__custom__'
    customCron.value = form.value.calc_cron || ''
  }
}

function onCronPresetChange(val: string): void {
  if (!form.value) return
  if (val === '__custom__') {
    customCron.value = form.value.calc_cron || ''
  } else {
    form.value.calc_cron = val
  }
}

function onCustomCronInput(val: string): void {
  if (form.value) {
    form.value.calc_cron = val
  }
}
```

- [ ] **Step 2: Call initCronState after loading config**

Update the `onMounted` callback (line 58-60) to also call `initCronState`:

```typescript
onMounted(async () => {
  form.value = await getGlobalConfig()
  initCronState()
})
```

- [ ] **Step 3: Replace cron template section**

Replace the cron form-item (lines 23-26):

From:
```vue
      <el-form-item label="规则引擎 cron">
        <el-input v-model="form.calc_cron" placeholder="0 8 * * *" />
        <span class="hint">默认每天 08:00 北京时间</span>
      </el-form-item>
```

To:
```vue
      <el-form-item label="规则引擎 cron">
        <el-select v-model="selectedCronPreset" style="width: 200px" @change="onCronPresetChange">
          <el-option
            v-for="preset in cronPresets"
            :key="preset.value"
            :label="preset.label"
            :value="preset.value"
          />
        </el-select>
        <el-input
          v-if="selectedCronPreset === '__custom__'"
          v-model="customCron"
          placeholder="0 8 * * *"
          style="width: 200px; margin-left: 12px"
          @input="onCustomCronInput"
        />
      </el-form-item>
```

- [ ] **Step 4: Verify build**

Run:
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: No new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/GlobalConfigView.vue
git commit -m "feat(ui): replace cron text input with preset dropdown and custom fallback"
```
