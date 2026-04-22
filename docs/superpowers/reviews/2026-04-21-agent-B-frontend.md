# Agent B — 前端 UX + 死代码审计

> Stage 1 / Agent B（主会话手动执行，因 agent 3 次 API 断连失败）
> 问题总数：16 条 / Critical: 0 / Important: 10 / Minor: 6

---

## Q1 — 前端交互 / 显示

### 问题 #1 — 采购/补货历史页 95% 代码重复

- 严重度：Important
- 位置：`frontend/src/views/history/ProcurementHistoryView.vue` vs `frontend/src/views/history/RestockHistoryView.vue`
- 现状：两个视图各 200+ 行、结构完全一致（`load` / `deleteOne` / `canDelete` / `statusTagType` / `onMounted` / 70 行 `<style scoped>`），只差 `CG-/BH-` 前缀、`procurement_display_status` vs `restock_display_status`、`procurement_snapshot_count` vs `restock_snapshot_count`、`type="procurement"` vs `type="restock"`、确认文案里"采购"/"补货"互换。任何一边改字段都要改两处，极易漂移。
- 建议：抽成单一 `SuggestionHistoryView.vue` + `type: SuggestionType` prop + computed 形态映射；或用一个 composable `useSuggestionHistory(type)` 拆掉 state/action 层重复。
- 工作量：M

### 问题 #2 — 历史页 `statusTagType` 用中文字面量做判断

- 严重度：Important
- 位置：`frontend/src/views/history/ProcurementHistoryView.vue:79-85`、`frontend/src/views/history/RestockHistoryView.vue:79-85`
- 现状：`if (status === '已导出') return 'success'` — 匹配字符串是后端返回的中文 i18n 标签。一旦后端改"已导出"→"导出完成"，前端 tag 颜色悄无声息变成默认 info。
- 建议：后端返回结构化 `{ code: 'exported' | 'pending' | 'archived', label }`，前端基于 `code` 判断；或前端维护 `STATUS_TAG_MAP` 常量但同样 key by code。
- 工作量：S（需要后端配合）

### 问题 #3 — 对话框关闭按钮样式不一致

- 严重度：Important
- 位置：`frontend/src/components/SuggestionDetailDialog.vue:7,26-34` vs `frontend/src/components/AppLayout.vue:151`、`frontend/src/views/RoleConfigView.vue:56-58`、`UserConfigView.vue:82-85` 等
- 现状：全站 6 个 el-dialog 里只有 `SuggestionDetailDialog` 用 `:show-close="false"` + 自定义 `<X :size="16" />` 按钮（为了在 header 塞下载按钮）。其他对话框都是 element-plus 默认 × 角落按钮。用户在两种视觉间切换会找不到关闭位置。
- 建议：要么让 `SuggestionDetailDialog` 也用默认 close（下载按钮放 footer），要么全站统一为自定义 header 按钮；至少保持位置一致（都在右上 12-16px 范围）。
- 工作量：M

### 问题 #4 — 历史详情弹框高度硬编码 500px

- 严重度：Important
- 位置：`frontend/src/components/SuggestionDetailDialog.vue:91,112`（el-table `max-height="500"`）+ `line 5` (`width="80%"`)
- 现状：大屏（1440p+）上 500px 把用户锁在固定窗口，必须滚动；小屏上 80% 宽度仍然过宽。两个维度都无响应式。
- 建议：`max-height` 改相对单位（如 `calc(100vh - 280px)`），`width` 加 @media 断点（桌面 80% / 平板 95% / 手机 fullscreen）。
- 工作量：S

### 问题 #5 — `DataInventoryView` 搜索框 placeholder 暴露后端字段名

- 严重度：Important
- 位置：`frontend/src/views/data/DataInventoryView.vue:6`
- 现状：`placeholder="commoditySku"`（驼峰式字段名直接暴露给用户）。对照 `DataProductsView.vue:6` "搜索 SKU / 商品名"、`DataWarehousesView.vue:5` "搜索仓库名/ID"、`ProcurementListView:10` "SKU 搜索"，全站都用中文 placeholder，此页是唯一异类。
- 建议：改为 "SKU 搜索" 或 "搜索 SKU"（和发起页对齐）。
- 工作量：S

### 问题 #6 — 发起页 empty 状态用同一条文案

- 严重度：Important
- 位置：`frontend/src/views/suggestion/ProcurementListView.vue:4,32`（`el-empty description="本期无采购需求"` + `el-table empty-text="本期无采购需求"`），`RestockListView:4,26` 同样双处 "本期无补货需求"
- 现状：用户搜索 SKU 无结果时，表格展示 "本期无采购需求" — 会让用户误以为整单都没东西，其实只是筛选不中。
- 建议：`el-empty` 用 "本期无采购需求"；`el-table empty-text` 基于当前过滤状态：关键字非空时 "未匹配到 SKU "keyword"，清除条件可看全部"；urgent-only 开启时 "当前无 30 天内紧急项"。
- 工作量：S

### 问题 #7 — 发起页 toolbar 结构在采购/补货两 Tab 不一致

- 严重度：Minor
- 位置：`ProcurementListView.vue:9-15` 用 `.table-toolbar__filters` wrapper div 包 SKU + 紧急开关；`RestockListView.vue:9` SKU 直接放在 `.table-toolbar` 下无 wrapper
- 现状：CSS 结构不对称，后续要在两边同时加筛选项就得改两处，且样式层级要同步。
- 建议：统一采用 `.table-toolbar__filters` 子容器（即使 restock 当前只有一个 SKU 也保留 wrapper），为未来扩展筛选项留位。
- 工作量：S

### 问题 #8 — 发起页表格未固定状态/操作列

- 严重度：Important
- 位置：`ProcurementListView.vue:29-69`、`RestockListView.vue:23-100`
- 现状：`el-table` 列宽总和可能超视口，横向滚动后"状态"列（采购量已付/未付等）脱出视口，用户失去关键上下文。对照历史页 `ProcurementHistoryView:32` 有 `fixed="right"`。
- 建议：`<el-table-column label="状态" ...>` 加 `fixed="right"`；编辑态下 `<el-table-column type="selection">` 加 `fixed="left"` 稳定勾选列位置。
- 工作量：S

### 问题 #9 — PurchaseDateCell 实际分 6 档但文档/命名写"5 档"

- 严重度：Minor
- 位置：`frontend/src/components/PurchaseDateCell.vue:46-52,81-89`；`docs/superpowers/reviews/2026-04-21-session-context.md`（"PurchaseDateCell 5 档"）
- 现状：代码注释"5 档分级"但 `levelClass` 返回 **6 种** class：`is-empty / is-overdue / is-today / is-warning / is-normal / is-loose / is-not-urgent`（实际是 7 档，把 empty 算上），等效 UI 层级 6 档（逾期/今日/临近/正常/宽松/不紧急）。
- 建议：更新 session-context 和代码注释为"6 档（+1 空态）"；或合并相邻档位减到 5 档（比如把"宽松"并入"不紧急"）。
- 工作量：S

### 问题 #10 — 数据页 filter 输入固定宽度缺响应式

- 严重度：Important
- 位置：`frontend/src/views/data/DataInventoryView.vue:8,12`、`DataShopsView.vue:4-5`、`DataWarehousesView.vue:5-6`、`DataProductsView.vue:6`、`DataOutRecordsView.vue:6-44`
- 现状：`<el-input style="width: 220px">` 类硬编码宽度在 < 600px 窄屏时挤爆 toolbar（同行 4-5 个输入）。`DataOrdersView.vue:429` 有 @media (max-width: 900px) 但其他数据页没有。
- 建议：① 把 toolbar 容器加 `flex-wrap: wrap` + `gap`；② 在 `<900px` 下 filter `width: 100%` 或 min-width 自动；③ 抽共用 `.filter-group` mixin。
- 工作量：M

### 问题 #11 — 历史页 delete 按钮 disabled 状态色值硬编码

- 严重度：Minor
- 位置：`ProcurementHistoryView.vue:198-201`、`RestockHistoryView.vue:196-198`
- 现状：`color: #b91c1c !important; box-shadow: 0 1px 2px rgba(220, 38, 38, 0.15);` — 硬编码 red-700 + 手写 rgba，不走 design token。
- 建议：加 `$color-danger-hover` / `$color-danger-shadow` 到 `frontend/src/styles/` 的 token 文件，复用。
- 工作量：S

### 问题 #12 — 文案用词细节不一致

- 严重度：Minor
- 位置：`AppLayout.vue:157` "至少6位" vs `UserConfigView.vue:109,197` "至少 6 位"（有空格）；`SuggestionListView.vue:25,34` "生成采补建议" vs "删除整单" vs 历史页 `deleteOne` 确认文案里"删除 采购建议单 CG-XXX"（空格诡异）
- 现状：同概念在不同页面用词不同，数字前后空格不统一。CJK + 数字/英文建议统一加空格。
- 建议：加一条 lint rule 或在代码评审时注意；抽 `COPY` 常量集中管理高频按钮文案。
- 工作量：S

---

## Q2 — 前端死代码

### 问题 #13 — `frontend/src/utils/allocation.ts` 整个文件无业务引用

- 严重度：Important
- 位置：`frontend/src/utils/allocation.ts`（3 个 export：`allocationModeLabel` / `allocationModeTagType` / `allocationSummary`）
- 现状：Grep `from '@/utils/allocation'` 全仓库**只有 `allocation.test.ts` 自身引用**，无任何 `.vue` 或业务 `.ts` 使用。对应的 `AllocationExplanation` 后端 schema 是否仍在流通也值得怀疑。
- 建议：删 `allocation.ts` + `allocation.test.ts`；或确认后端有场景会返回 `allocation_mode`（比如详情弹框的 `restock` 类型），缺前端消费位再补。需要 Agent C / A 交叉验证后端 schema 是否仍声明 `AllocationExplanation`。
- 工作量：S

### 问题 #14 — `DataInventoryView.test.ts:61` 2 个 `no-useless-escape` eslint error

- 严重度：Minor
- 位置：`frontend/src/views/__tests__/DataInventoryView.test.ts:61`
- 现状：ESLint `no-useless-escape`（字符串字面量里多余的 `\"`），inventory Stage 0 已发现。
- 建议：去掉 `\"` 转义（改成单引号字符串或不转义 " 即可）。
- 工作量：S

### 问题 #15 — `SuggestionListView` 的 `totalSnapshotCount` computed 仅单处使用

- 严重度：Minor
- 位置：`frontend/src/views/SuggestionListView.vue:115-119`、使用处 `line 140`
- 现状：独立 computed 只被 `statusMeta` 使用一次，可内联 `(procurement_snapshot_count ?? 0) + (restock_snapshot_count ?? 0)`；非死代码但算冗余。
- 建议：内联或保留（如预期未来多处复用，保留更好；目前没有复用）。
- 工作量：S

### 问题 #16 — `RestockListView` 声明 `editable` 但无编辑 UI

- 严重度：Minor
- 位置：`frontend/src/views/suggestion/RestockListView.vue:169`（`const editable = computed(() => ... 'draft')`）
- 现状：`editable` 仅用于条件渲染勾选列（`type="selection"`）和导出按钮。补货 Tab 下**没有**可直接编辑补货量/国家分布/仓库分配的 UI（对比采购 Tab 有 `purchase_qty` / `purchase_date` 可编辑）。代码不是死代码（`editable` 被用），但"draft 态可编辑"的用户心智和实际不一致。
- 建议：要么补上补货量编辑 UI（需要和产品确认是否支持编辑仓库分配），要么显式说明补货 Tab 仅提供勾选+导出，在 UI 里加 hint 避免用户等待编辑入口。需 Agent C 确认 `specs/` 规格如何描述。
- 工作量：S（文档）/ L（补编辑 UI）
