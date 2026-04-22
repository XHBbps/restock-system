# Agent D — 性能瓶颈审计

> Stage 1 / Agent D（主会话手动执行，因 agent 2 次 API 断连失败 — 分别 18 min / 30 min 后 socket error）
> 问题总数：11 条 / Critical: 0 / Important: 6 / Minor: 5

---

## Q1 — 后端性能

### 问题 #1 — 增长型表 `task_run` / `inventory_snapshot_history` 无 retention / purge 机制

- 严重度：Important
- 位置：`backend/app/tasks/jobs/daily_archive.py` + `backend/app/tasks/reaper.py`（均不包含 retention 逻辑）
- 现状：Grep `def clean|def archive|def purge|def cleanup|def delete_old` 在 `backend/app/tasks/**` 返回 0 match。`daily_archive.py` 从名字看是"归档 suggestion"但不清理 `task_run` 或 `inventory_snapshot_history`。
  - `task_run`：每次同步 / 引擎 / 刷新 dashboard 都写一行，假设每小时 1 sync job + 每天 1 calc + 刷新若干，5 年累计 ~30-50 万行
  - `inventory_snapshot_history`：每次库存同步写 N 行（N = SKU × 仓库），假设 100 SKU × 3 仓 × 每天 24 次同步 = 7200 rows/day × 5 年 ≈ 1300 万行
  - 索引良好（见下），查询扫描 OK，但表膨胀会让 `VACUUM` / 备份越来越慢，dev DB 现已有 2964 行 history + 427 行 task_run（5 天数据）
- 建议：加 `app/tasks/jobs/retention.py` cron 任务 —
  - `task_run`：保留 `created_at >= now() - interval '90 days'`（或按 status 区分 — success 保留短、failed 保留长）
  - `inventory_snapshot_history`：按 `snapshot_date` 压缩，保留最近 N 天逐日快照 + 历史按月/季度聚合一行
- 工作量：M

### 问题 #2 — `deploy/data/exports/` Excel 文件累积无清理

- 严重度：Important
- 位置：`backend/app/services/excel_export.py` + `deploy/docker-compose.*.yml`（只 mount 无清理）
- 现状：每次导出 snapshot 在 `/app/data/exports/{yyyy}/{mm}/` 写 Excel 文件，**无对应删除**。`excel_export_log` 有记录但文件本身只增不减。dev DB 当前仅 212 KB，但生产每天可能 5-20 份导出（采购 + 补货 × 每日 N 轮），一年累计 GB 级。Session-context 提示 #1 原话。
- 建议：加 `app/tasks/jobs/exports_retention.py`：保留最近 N 份（如 30 天）；超期删除文件 + 把 `excel_export_log` 对应行的 `file_path` 置 NULL / 加 `file_purged_at` 时间戳。下载 API 遇到 purged 文件返回 410 Gone 并提示用户。
- 工作量：M

### 问题 #3 — Dashboard `_country_sale_days` 和相关 metrics 每次 API 调用重算

- 严重度：Important
- 位置：`backend/app/api/metrics.py` 整体 + `dashboard_snapshot.payload` 手动刷新机制
- 现状：session-context 提示 #4："`dashboard_snapshot.payload` 的 EU 迁移 — 手动刷新快照才生效；有没有自动失效机制？" 阅读 `metrics.py:80-82` 确认 `snapshot_status: Literal["ready", "missing", "refreshing"]` 表明读取是 snapshot 缓存模式。但：
  - 当前 snapshot 生成靠手动点"刷新快照"按钮（Workspace）或定时刷新任务
  - 如果 EU 成员国变更（global_config 改动）/ 国家别名重定义，dashboard snapshot **不会自动失效**，用户看到过期数据直到手动刷新
  - PROGRESS.md 也未提 auto-invalidate 机制
- 建议：两个方向可选 —
  - **事件驱动失效**：`config.py` 更新 EU countries / restock_regions 时，把 `dashboard_snapshot` 标 `stale = true`（加字段），下次 `GET /api/metrics/dashboard` 发现 stale → 自动入队刷新任务（dedupe 保护避免并发）
  - **TTL 失效**：给 snapshot 加 `expires_at`，过期后 `snapshot_status="missing"` 触发重算
- 工作量：M

### 问题 #4 — 引擎 step5 仓库分配批量加载已优化 ✅ 非问题（信息项）

- 严重度：Minor
- 位置：`backend/app/engine/step5_warehouse_split.py:71-116`
- 现状：`load_all_sku_country_orders` 明确注释 "规则引擎 runner 用一次查询替代 NxM 次"，单次 IN 查询 + 内存分组，符合宪法 V 原则。`split_country_qty` / `explain_country_qty_split` 都是纯内存计算。✅
- 建议：无需修改；记录以阻止后续 agent 重复报告。
- 工作量：—

### 问题 #5 — `sync/order_detail.py` 有 7 处 `await db.execute|commit|refresh` 需关注事务粒度

- 严重度：Minor
- 位置：`backend/app/sync/order_detail.py`
- 现状：grep 返回 7 处 db.execute / commit / refresh 调用，结合 PROGRESS.md 描述"按 2 QPS / 2 并发保守抓取" + "已完成 X / 失败 Y / 总数 N 持续回写精确进度" — 每条订单详情的抓取和写入可能都跟着一次 commit，这会在高 N 时显著拖慢（每 commit = 一次 PostgreSQL fsync）。未展开完整文件深读，仅作提示。
- 建议：Agent D 后续或 Stage 3 做代码 deep dive 确认是否 batch commit；如果真的 per-row commit，改为每 N 条（比如 50 条）commit 一次 + progress 更新间隔放宽。
- 工作量：S（查证）/ M（改 batch）

### 问题 #6 — `api/suggestion.py::list_suggestions` 使用 subquery join 避免 N+1 ✅

- 严重度：Minor（信息项）
- 位置：`backend/app/api/suggestion.py:91-133`
- 现状：`procurement_snapshot_count_sq` / `restock_snapshot_count_sq` 作为 correlated scalar subquery，通过 `add_columns(...)` 合并进主查询，一次性拿 list + 两种 snapshot count。不是 N+1。Session-context 提示 #6 的担心在此处不成立。✅
- 建议：无。
- 工作量：—

---

## Q2 — 前端性能

### 问题 #7 — Bundle chunk 906 KB / 557 KB 已是 manualChunks 后的理论下限

- 严重度：Important
- 位置：`frontend/vite.config.ts:45-70` + `frontend/src/components/charts/BaseChart.vue:17-19`
- 现状：
  - `vite.config.ts` 已配 `manualChunks`：`charts` / `element-plus` / `framework` 三个路径
  - `BaseChart.vue` 已按需 import（`import { BarChart, LineChart, PieChart } from 'echarts/charts'` + `CanvasRenderer`）— 不是全量 echarts
  - Element Plus 用 `unplugin-auto-import` + `unplugin-vue-components`（`ElementPlusResolver({ importStyle: false })`）理论上 tree-shaking 工作
  - **906 KB element-plus 大概率是**：系统用了大量 el-table / el-input / el-dialog / el-select / el-form 等"重量级"组件，这些组件各自依赖了 popper.js / virtual scroll / internal transitions 等，element-plus 内部模块耦合让 tree-shake 只能去掉 "完全没用" 的，没法裁掉"部分用"的
  - **557 KB charts** 同理，BarChart/LineChart/PieChart 三种图表 + canvas renderer + 相关 components（Title / Tooltip / Legend / Grid）本身就这么大
- 建议：
  - **短期**：调 `chunkSizeWarningLimit: 1000` 消除警告，实际体积下降空间有限
  - **中期**：按路由更细拆 manualChunks — 把 `charts` 再按页面拆（`charts-workspace`, `charts-monitor`, `charts-sync`），每页只加载自己用的 chart 类型组合；但 BaseChart 共享组件统一用 `BarChart/LineChart/PieChart` 三种的话就没拆的意义
  - **长期（价值不大）**：换更轻的 UI 库（Naive UI 约 400 KB）或更轻的 chart 库（Chart.js 约 180 KB），但迁移成本 > 瘦身收益
  - 这个项目规模（1-5 用户内网）**bundle 大小不是瓶颈**，首屏已有路由懒加载，接受现状即可
- 工作量：S（调 warning limit）/ L（深度瘦身）

### 问题 #8 — `index-*.js` 主 entry 55.77 KB 来源未验证

- 严重度：Minor
- 位置：`frontend/src/main.ts` / `frontend/src/App.vue`（未读）+ build 产物 `index-B1MqI-ja.js`
- 现状：vite build 报 `index-B1MqI-ja.js 55.77 KB / gzip 21.21 KB`。按路由懒加载后主 entry 应仅包含 App / router / pinia store / 全局 middleware。55 KB 是合理的，但若其中含 workspace 相关 code（因为 default 路由可能是 workspace），会把"首页代码"固定进主 bundle。
- 建议：如需优化，用 `npx vite-bundle-visualizer`（需装）或在 `vite.config.ts` 加 `rollup-plugin-visualizer` 看 entry 内容；默认路由的页面单独保持懒加载（router 配置看是否指向懒 component）。
- 工作量：S（检查）

### 问题 #9 — 数据页"一次拉 5000 行 + 前端筛选 + 本地分页"策略的体积注意

- 严重度：Minor（信息项，遵循 CLAUDE.md 规则）
- 位置：CLAUDE.md 原则 + `DataInventoryView.vue` / `DataOrdersView.vue` 等
- 现状：CLAUDE.md 约定 "一次拉全量 + 前端筛选 + 本地分页（page_size=5000）"。这意味着每个数据页首次加载会拉 5000 行 JSON 到浏览器。以 orders 为例，单行约 1 KB 则单页首载 5 MB 未压缩 JSON。现场 orders 表 `dev DB` 当前 0 行，生产量级未知。
- 建议：
  - 保持现状（项目规则），但监控每个数据表行数，接近 5000 时考虑拆 virtual scroll 或真正后端分页
  - 关键：给 `el-table` 加 `virtual` 属性（Element Plus 4 支持），防止 DOM 渲染 5000 行导致浏览器主线程卡顿（这是比网络体积更严重的问题）
- 工作量：M

### 问题 #10 — 大列表页已有后端分页 ✅ 非问题（信息项）

- 严重度：Minor（信息项）
- 位置：PROGRESS.md §2.5 / `HistoryView.vue` / `DataOrdersView.vue`
- 现状：PROGRESS.md 明确"订单、历史、商品、库存、出库记录等高增长页面已切换为后端分页"。`ProcurementHistoryView.vue` / `RestockHistoryView.vue` 的 `TablePaginationBar` 绑定 `page` / `pageSize` / `total` 并调 API，是真正的后端分页。✅
- 建议：无。
- 工作量：—

---

## Q3 — DB 性能

### 问题 #11 — `task_run` / `inventory_snapshot_history` 索引设计良好 + JSONB 字段无 GIN

- 严重度：Important
- 位置：`docker exec psql \d+ task_run` / `\d+ inventory_snapshot_history` 实测 + `backend/app/models/suggestion.py`、`suggestion_snapshot.py`
- 现状：
  - **`task_run` 索引齐全**（partial + composite）✅ `ix_task_run_job_created(job_name, created_at)` / `ix_task_run_lease(lease_expires_at) WHERE status='running'` / `ix_task_run_pending_priority(status, priority, created_at) WHERE status='pending'` / `uq_task_run_active_dedupe` — partial index 非常专业
  - **`inventory_snapshot_history` 索引齐全** ✅ 双向 composite `(snapshot_date, commodity_sku)` 和 `(commodity_sku, snapshot_date)`
  - **JSONB 字段 GIN 索引检查**：
    - `suggestion.global_config_snapshot` / `suggestion.context_json` — 没有 GIN（但查询都按 suggestion_id 主键检索，不会按 JSONB key 过滤）
    - `suggestion_snapshot.payload` / `suggestion_snapshot_item.payload` — 同理（按 snapshot_id / suggestion_id 检索）
    - `dashboard_snapshot.payload` — 是单行表（global），不按 key 搜
    - `task_run.payload` / `task_run.result_payload` — 按 task id / job_name 检索
  - **结论**：所有 JSONB 都只"当作字典写入、整体取出"，**不需要** GIN / expression index ✅
- 建议：保持现状；如果未来加 "按 JSONB key 过滤" 的需求（如 `WHERE payload->>'shop_id' = '...'`），再补 expression index。`pg_stat_statements` 开启可通过 Agent E 推的 `validate_env.sh` 阶段启用 — 暂不紧急。
- 工作量：—

---

## 总结（Agent D 视角）

- **设计层面**：引擎 step5 批量加载、API 层 scalar subquery、DB 索引 partial/composite 策略都是成熟设计，**核心代码路径没有明显 N+1 或索引缺失**
- **运维层面**：**3 个增长型数据源**（task_run / inventory_snapshot_history / exports/*.xlsx）都缺 retention 机制 — 这是最实际的"未来 6-12 个月会痛"的债
- **前端 bundle**：906 KB / 557 KB **是理论下限附近**，继续拆边际收益低；放 warning limit 比硬瘦身实用
- **Dashboard snapshot**：手动刷新模式有过期风险（session-context 提示 #4 确认），应加自动失效或 TTL
