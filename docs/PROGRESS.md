# Restock System 项目进度

> 最近更新：2026-04-11
> 本文档记录已交付能力和近期重大变更。架构细节见 [`Project_Architecture_Blueprint.md`](Project_Architecture_Blueprint.md)。

---

## 1. 总体状态

| 维度 | 状态 |
|---|---|
| 主链路 | 打通 — 赛狐同步 → 补货计算 → 建议编辑 → 采购单推送 |
| 工程化 | 运行时配置校验、健康检查、部署脚本、CI 骨架、测试覆盖已就绪 |
| 前端 | 已统一到 `PageSectionCard` + 本地分页模式，设计系统对齐 shadcn Zinc |
| 后端 | 三服务进程分离（backend / worker / scheduler），TaskRun 队列稳定运行 |

---

## 2. 已交付能力

### 2.1 后端与部署

- **配置校验**：生产环境强制要求关键密钥与赛狐凭证
- **健康检查**：
  - `GET /healthz` — 进程存活
  - `GET /readyz` — 按进程角色检查数据库 + worker + reaper + scheduler
- **部署脚本**（`deploy/scripts/`）：
  - `deploy.sh` — 完整发布流程（备份 → 迁移 → 镜像 → smoke check → 失败回滚）
  - `migrate.sh` / `pg_backup.sh` / `restore_db.sh` / `rollback.sh` / `validate_env.sh` / `smoke_check.sh`
- **进程角色解耦**：通过 `PROCESS_ENABLE_WORKER/REAPER/SCHEDULER` 将 backend 镜像拆为 3 个服务
  - `backend` — 仅 HTTP API
  - `worker` — 任务执行 + 僵尸回收
  - `scheduler` — 定时入队
- **资源限制**（`docker-compose.yml`）：db 1G、backend 512M、worker 512M、scheduler 512M、frontend 256M、caddy 128M

### 2.2 同步与调度

- **调度器开关**：`GET/POST /api/sync/scheduler`，开关状态持久化到 `global_config.scheduler_enabled`
- **调度参数实时生效**：`sync_interval_minutes`、`calc_cron` 保存后立即 reload
- **cron 校验**：非法表达式在保存前拦截
- **手动触发**：`POST /api/sync/shop` 及其他 sync 端点
- **自动同步任务**（APScheduler 间隔触发）：
  - `sync_product_listing` / `sync_inventory` / `sync_out_records` / `sync_order_list` / `sync_order_detail`
- **定时任务**（cron，Asia/Shanghai）：
  - 03:30 `sync_warehouse`
  - 02:00 `daily_archive`
  - 默认 08:00 `calc_engine`（可配置，`calc_enabled` 控制）
- **订单详情并发拉取**：`sync_order_detail` 支持 3 个并发（与 `/api/order/detailByOrderId.json` 的 3 QPS 限额对齐）

### 2.3 补货计算引擎

- **6 步流水线**（`backend/app/engine/runner.py`）：
  1. `step1_velocity` — 加权日均销量（7日×0.5 + 14日×0.3 + 30日×0.2）
  2. `step2_sale_days` — 可售天数 + 库存聚合（含在途）
  3. `step3_country_qty` — 各国补货量
  4. `step4_total` — 总采购量（扣减国内库存 + 缓冲天数）
  5. `step5_warehouse_split` — 按邮编规则分配到具体仓库
  6. `step6_timing` — 建议采购日 / 发货日 / 紧急标志
- **并发保护**：`pg_advisory_xact_lock(7429001)` 事务级锁，阻止并发引擎覆盖彼此
- **在途去重**：`load_in_transit` 基于已推送（未归档）建议条目的 `country_breakdown`，避免生成新建议时重复补货（近 90 天窗口）
- **快照追溯**：`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot` 存入 JSONB 字段

### 2.4 补货建议管理

- **建议单**：`draft/partial/pushed/archived/error` 状态流转
- **跨页选择**：补货发起页的 `selectedIds` 数组跨分页保持，支持全选筛选后的所有条目
- **编辑校验**：仅当同时提交 `total_qty` 和 `country_breakdown` 时才做一致性校验
- **推送到赛狐**：`pushback/purchase.py` 合并选中条目生成采购单，失败自动重试
- **去重**：同一 suggestion 同时只有一个 push 任务（`dedupe_key="push_saihu#<id>"`）

### 2.5 前端 Dashboard 体系

- **统一页面容器**：所有列表页使用 `PageSectionCard`（`#title` + `#actions` slot）
- **共享工具模块**：
  - `frontend/src/utils/format.ts` — 时间格式化（`formatShortTime` / `formatDateTime` / `formatDetailTime`）和分页工具（`clampPage`）
  - `frontend/src/utils/warehouse.ts` — 仓库类型标签和标签类型
  - `frontend/src/utils/countries.ts` — 国家代码映射
  - `frontend/src/utils/status.ts` — 状态元数据
  - `frontend/src/utils/tableSort.ts` — 排序工具
- **Dashboard 复用组件**：
  - `DashboardPageHeader` / `DashboardStatCard` / `DashboardSection` / `DashboardChartCard` / `DataTableCard`
  - `BaseChart`（ECharts 封装）
- **数据加载模式**：所有数据页统一使用"一次拉全量 + 前端筛选 + 本地分页"，`page_size=5000`
- **筛选控件高度统一**：`PageSectionCard` 的 `section-actions` 强制所有控件 32px 高度
- **订单状态中文映射**：`DataOrdersView.vue` 添加 `ORDER_STATUS_LABEL`（已发货 / 部分发货 / 未发货 / 待处理 / 已取消）

### 2.6 数据管理

- **仓库国家变更级联**：修改 `warehouse.country` 时同步更新 `inventory_snapshot_latest` 对应记录，无需等下次同步
- **仓库国家支持清除**：下拉框加 `clearable`，后端 schema 支持 `null`
- **数据页 page_size 上限放宽**：所有 `/api/data/*` 端点的 `le=5000`（原 200），支持一次拉全量
- **建议单列表 page_size 上限**：`/api/suggestions` 的 `le=5000`
- **筛选项统一**：店铺/仓库/订单/库存/出库/补货发起 7 个页面的筛选项布局和高度一致

### 2.7 任务队列系统

- **`task_run` 表**：dedupe_key 去重（partial unique index）、priority 调度、lease 心跳
- **Worker** 2 秒轮询 + 30 秒心跳 + 2 分钟租约
- **Reaper** 60 秒扫描过期任务
- **任务进度实时写入**：`current_step` / `step_detail` / `total_steps`，前端 `TaskProgress` 轮询展示
- **SKIPPED 状态**：调度器尝试重复入队活跃任务时创建审计记录

### 2.8 认证与安全

- **JWT HS256**：24 小时有效，单用户 `sub="owner"`
- **登录锁定按 IP 隔离**：从全局共享改为来源 IP 粒度，优先读 `X-Forwarded-For`/`X-Real-IP`
- **新增表**：`login_attempt`（迁移 `20260409_1710_add_login_attempt.py`）
- **API 调用日志**：每次赛狐调用都写 `api_call_log`

---

## 3. 近期重大变更（2026-04-10 ~ 2026-04-11）

### 3.0 push 端点状态机封闭性修复（2026-04-11，云交付评分卡 M3 阶段）

- `POST /api/suggestions/{id}/push` 添加状态前置校验：`sug.status not in ("draft","partial")` 时抛 `ConflictError("建议单状态为 X,不可推送")`
- 修复点：`backend/app/api/suggestion.py:274-275`
- 背景：审计中发现 PATCH 端点严格拒绝 archived 而 push 端点不检查的不对称缺陷，可能导致对已归档/已完全推送建议单触发重复采购单
- 新增 2 个单测：`test_suggestion_push_archived_rejected` / `test_suggestion_push_pushed_rejected`，全 backend 156 单测通过
- 评分影响：M3 D6 维持 3，M3 P0-2 候选从"⚠️ 部分实现"升级为"✅ 已实现"

### 3.1 Overstock 特性移除

全栈清理：
- 删除 `frontend/src/views/OverstockView.vue`、导航入口、路由
- 删除 `backend/app/models/overstock.py` 和 `overstock_sku_mark` 表
- 删除 `suggestion_item.overstock_countries` 字段
- 删除 `/api/monitor/overstock` 端点
- 引擎 `step3_country_qty` 不再收集 overstock 数据
- initial migration 同步更新

### 3.2 架构蓝图文档

- 新增 `docs/Project_Architecture_Blueprint.md`（~700 行）
- 包含分层架构图、6 步引擎流水线详解、任务队列机制、赛狐集成模式、ADR 摘要、扩展指南

### 3.3 代码复用重构

- 抽取 `utils/format.ts` 和 `utils/warehouse.ts`，消除 14 处重复定义
- `formatTime` / `clampPage` / `warehouseTypeLabel` / `warehouseTypeTag` 统一实现

### 3.4 并发与性能优化

- **订单详情拉取**：串行改并发（`asyncio.Semaphore(3)` + `asyncio.gather`），充分利用 3 QPS 额度
- **后端端点 page_size**：5 个 data 端点 + suggestions 端点从 `le=200` 放宽到 `le=5000`
- **前端数据页**：改为一次拉取全量，前端本地分页

### 3.5 配置变更影响提示

- **全局参数**保存后：若 `target_days` / `buffer_days` / `lead_time_days` 任一变更，前端警告"建议重新生成补货建议单"
- **仓库国家**修改后：前端警告 + 同步更新库存表
- **邮编规则**变更：不加提示（仅影响仓库分配展示，不影响采购量）

### 3.6 UX 改进

- Checkbox 勾选标记改用 SVG background-image 精确居中
- Tooltip 淡出动画 300ms → 100ms，避免快速移动时堆叠
- 筛选项高度统一 32px
- 全选跨页保持 + 推送上限放宽（原 50 条上限已移除）
- 表格排序图标列宽修复

### 3.7 引擎逻辑修复

- **H4 一致性校验**：仅当同时提交 `total_qty` 和 `country_breakdown` 时才校验
- **step3**：返回类型从 `tuple[dict, dict]` 简化为 `dict[str, dict[str, int]]`
- **load_in_transit 启用**：从 stub 改为实际查询已推送建议

### 3.8 赛狐订单详情接口特殊限流

- `/api/order/detailByOrderId.json` 独立配置 3 QPS（其他接口维持默认 1 QPS）
- 通过 `saihu/rate_limit.py` 的 `_ENDPOINT_RATE_OVERRIDES` 映射

### 3.9 zipcode_matcher 鲁棒性

- `_compare` 函数在 `value_type == "number"` 分支中初始化 `compare_values = []`
- 防止 DB 中意外存在 `number+contains` 组合导致的 `UnboundLocalError`

### 3.10 编码问题修复

- `ApiMonitorView.vue` 和 `SuggestionListView.vue` 中的乱码字符串修复
- 全项目 grep 确认 0 残留乱码

### 3.11 筛选体系完善

| 页面 | 新增筛选 |
|---|---|
| 店铺 | 关键字搜索、区域下拉 |
| 仓库 | 关键字搜索、类型下拉 |
| 订单 | 店铺下拉 |
| 库存 / 出库 | 国家文本框 → 下拉 |
| 补货发起 | 推送状态下拉 |

### 3.12 订单详情失败分类修复

`sync_order_detail` 原本把所有 `SaihuAPIError` 子类都当作永久失败写入 `order_detail_fetch_log`，导致限流 / 网络 / auth 过期等瞬时错误在一次重试预算耗尽后被永久拉黑，再也无法补拉。

- **分类器**：新增纯函数 `_is_permanent_saihu_error`，仅 `SaihuBizError` 返回 `True`；`SaihuRateLimited` / `SaihuNetworkError` / `SaihuAuthExpired` / 裸 `SaihuAPIError` 全部视为瞬时，不写日志 → 下一轮调度自动重试
- **`_fetch_one` 改造**：日志事件拆成 `order_detail_fetch_permanent_failure`（含 `saihu_code`）与 `order_detail_fetch_transient_failure` 两条，方便 ops 区分
- **测试**：`backend/tests/unit/test_sync_order_detail_classification.py` 6 个用例锁定分类规则
- **历史清理**：alembic `20260411_1000` 数据迁移一次性删除 `http_status IS NULL AND (saihu_code IS NULL OR saihu_code IN (40001, 40019))` 的误拉黑记录；downgrade 为空
- **部署提示**：执行该 migration 前建议先暂停 APScheduler（`scheduler_enabled=false`），避免 DELETE 与并发 UPSERT 抢锁

### 3.13 邮编规则新增 `between` 区间运算符

- 2026-04-11 — 邮编规则新增 `between` 区间运算符：`compare_value` 支持单段 `"000-270"` 或多段 `"000-270, 500-700"`，一条规则即可表达闭区间，仅 `value_type=number` 允许。后端迁移 `20260411_1500` 将 `zipcode_rule.operator` 由 `String(5)` 扩到 `String(10)`、`compare_value` 由 `String(50)` 扩到 `String(200)`，`operator_enum` CHECK 约束新增 `'between'`。前后端校验对齐（段数 ≤ 20；`hi ≤ 10^prefix_length - 1`）。

---

## 4. 已验证

### 4.1 后端

- `cd backend && .\.venv\Scripts\python.exe -m pytest`：**117 passed, 2 skipped**（集成测试需要 TEST_DATABASE_URL）
- 关键测试：
  - `tests/unit/test_engine_step1.py` ~ `test_engine_step6.py`
  - `tests/unit/test_zipcode_matcher.py`
  - `tests/unit/test_auth_login.py`
  - `tests/unit/test_scheduler_api.py`
  - `tests/unit/test_health_endpoints.py`
  - `tests/unit/test_config_schema.py`
  - `tests/unit/test_runtime_settings.py`
  - `tests/unit/test_sku_init.py`

### 4.2 前端

- `cd frontend && npx vue-tsc --noEmit`：类型检查通过
- `cd frontend && npx vite build`：构建成功（~10 秒）
- `cd frontend && npm run test`：Vitest 通过

### 4.3 SKU 配置初始化

- `product_listing_total = 304`
- `sku_config_created = 118`
- `sku_config_enabled = 118`
- 引擎验证：`suggestion_id = 1` 生成了 91 条建议

---

## 5. 后续计划

### 短期

- 继续沉淀高频页面到 `DashboardPageHeader + DataTableCard` 体系
- 监控页补充趋势型聚合接口
- 前端 vendor chunk 进一步细分

### 中期

- 数据页数据量增长后切换为 server-side 分页（当前 1-5 用户场景无压力）
- 研究 HEI（历史建议 In-Transit）窗口是否需要调整（当前 90 天）

### 长期（按需）

- 若需多机部署：引入外部分布式锁替代 `pg_advisory_xact_lock`
- 若需多 worker：评估 Celery 迁移成本

---

## 相关文档

- [架构蓝图](Project_Architecture_Blueprint.md) — 分层架构、组件职责、ADR
- [部署指南](deployment.md) — 发布流程和环境变量
- [运维手册](runbook.md) — 故障排查和监控
- [新成员入门](onboarding.md) — 本地开发和工作流
