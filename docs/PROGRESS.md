# Restock System 项目进度

> 最近更新：2026-04-13（订单页“详情获取”组件化与订单详情抓取并发收口）
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
- **订单详情同步与详情获取**：`sync_order_detail` 当前按 2 QPS / 2 并发保守抓取；订单页提供右侧独立“详情获取”组件，仅提供天数选择与触发按钮；手动触发会优先复用活跃的 `refetch_order_detail`、`sync_order_detail` 或 `sync_all` 任务，避免并发重复抓取

### 2.3 补货计算引擎

- **6 步流水线**（`backend/app/engine/runner.py`）：
  1. `step1_velocity` — 加权日均销量（7日×0.5 + 14日×0.3 + 30日×0.2）
  2. `step2_sale_days` — 可售天数 + 库存聚合（含在途）
  3. `step3_country_qty` — 各国补货量
  4. `step4_total` — 总采购量（扣减国内库存 + 缓冲天数）
  5. `step5_warehouse_split` — 按邮编规则分配到具体仓库
  6. `step6_timing` — 建议采购日 / 紧急标志
- **并发保护**：`pg_advisory_xact_lock(7429001)` 事务级锁，阻止并发引擎覆盖彼此
- **快照追溯**：`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot` 存入 JSONB 字段

### 2.4 补货建议管理

- **建议单**：`draft/partial/pushed/archived/error` 状态流转
- **跨页选择**：补货发起页的 `selectedIds` 数组跨分页保持，支持全选筛选后的所有条目
- **编辑校验**：建议详情支持编辑 `total_qty` / `country_breakdown` / `warehouse_breakdown` / `t_purchase`；国家补货量不要求与总采购量一致，已配置仓库时仓内分量之和必须等于国家补货量；正补货量国家未显式填写 `t_purchase` 时后端默认当天
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
  - `frontend/src/utils/monitoring.ts` — 监控页名称映射、分位点工具和任务反馈文案
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
- **出库记录页**：原“其他出库（在途观测）”改名为“出库记录”；主表展示出库单id、出库仓库id、更新时间、出库单类型、状态，明细展示商品id、商品sku、可用数、采购单价；状态统一按 `is_in_transit` 映射为“在途 / 完结”

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

## 3. 近期重大变更（2026-04-10 ~ 2026-04-13）

### 3.19 出库记录字段补齐（2026-04-13）
- `backend/app/sync/out_records.py` 在同步赛狐其他出库记录时，额外落库 `warehouseId`、`updateTime`、`type`、`typeName`，并为明细落库 `commodityId`、`perPurchase`
- `backend/alembic/versions/20260414_1300_extend_in_transit_out_record_fields.py` 为 `in_transit_record` / `in_transit_item` 补齐上述展示字段，支撑数据页直接展示源字段含义
- `backend/app/api/data.py`、`backend/app/schemas/data.py` 与 `frontend/src/api/data.ts` 补齐对应 DTO；出库记录列表默认按 `updateTime desc` 返回，并支持按出库仓库id、更新时间、出库单类型排序
- `frontend/src/views/data/DataOutRecordsView.vue` 将页面标题改为“出库记录”，主表和明细表按最新业务口径展示字段，状态标签统一为“在途 / 完结”
- **测试**：补充 `backend/tests/unit/test_sync_out_records_job.py`、`backend/tests/unit/test_data_out_records_api.py` 与 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖同步落库、列表排序和页面默认请求/字段渲染

### 3.18 订单详情条件批量获取（2026-04-13）

- `backend/app/api/sync.py` 的 `POST /api/sync/order-detail/refetch` 改为订单详情抓取统一入口：若存在活跃的 `refetch_order_detail`、`sync_order_detail` 或 `sync_all`，则直接返回现有任务供前端复用进度；否则再按回溯天数筛选“订单主表已存在但本地缺少详情”的订单并创建后台任务
- `backend/app/sync/order_detail.py` 的 `refetch_order_detail` 继续绕过 `order_detail_fetch_log` 的已记录过滤，直接消费接口层筛出的订单集合，但仍复用现有详情抓取、失败分类、限流与落库逻辑
- `frontend/src/components/sync/OrderDetailFetchAction.vue` 将订单页入口封装为右侧独立“详情获取”组件；`frontend/src/views/data/DataOrdersView.vue` 只负责承接任务进度和列表刷新
- **测试**：补充 `backend/tests/unit/test_scheduler_api.py`、`frontend/src/components/sync/OrderDetailFetchAction.test.ts` 与 `frontend/src/api/__tests__/sync.test.ts`，覆盖活跃任务复用、详情获取入口提示、手工触发 payload 与空命中不建任务

### 3.17 监控名称中文化（2026-04-13）
- `frontend/src/utils/monitoring.ts` 新增统一名称映射：赛狐接口 `endpoint`、性能监控 `request/resource` 名称统一转为中文含义，并保留原始路径用于 tooltip 排障
- `frontend/src/views/ApiMonitorView.vue` 与 `frontend/src/components/sync/FailedApiCallTable.vue` 改为在“接口监控”和“同步日志”中主显示中文接口名称，图表 tooltip 同步展示中文名和原始接口
- `frontend/src/views/PerformanceMonitorView.vue` 改为将“请求名称”“资源名称”按内部接口、页面导航、Vite 资源、静态资源分组中文化展示，同时保持按原始路径聚合，避免不同资源因中文重名被错误合并

### 3.16 全链路 Review 修复收尾（2026-04-13）
- `backend/app/sync/product_listing.py` 改为拉取全量 listing（不再强制 `match=true` + `onlineStatus=active`）；本地 `product_listing` 允许保存未匹配行，并用 `is_matched` 标识；引擎读取 `commodity_id` 时继续只消费 active + matched 的行
- `backend/app/sync/product_listing.py` 在商品同步落库后会自动补齐缺失的 `sku_config` 行；商品页可看到全部 SKU，但仅 `is_matched=true && online_status=active` 的 SKU 会被自动置为 `enabled=true` 进入引擎，其余 SKU 默认创建为禁用态
- `frontend/src/views/data/DataProductsView.vue` 改为通过统一状态映射判断 listing `online_status`；商品页现在按大小写无关方式识别 `active`，不会再把后端已标准化为小写的在售商品误显示成“不在售”
- `SuggestionDetailView` 改为支持编辑 `total_qty`、国家补货量、仓库拆分、采购时间；移除发货时间，国家补货量不再要求与总采购量一致，仓内分量仍需对齐国家补货量

### 3.15 全链路 Review 修复（2026-04-12）

审查范围：引擎链路 + 数据同步 + 任务队列 + 推送 + API + 前端 + 部署。28 项发现，16 个 Task 已修复。

**Phase 1 — 数据正确性：**
- P0-1: Step4 国内库存不参与扣减 — 确认 by design，添加业务意图注释
- P0-2: 引擎取整策略统一为 `math.ceil()`（数量）/ `round()`（日期偏移）
- P0-3: `SuggestionItemPatch` 添加 `country_breakdown` / `warehouse_breakdown` 非负校验
- P0-4: 推送失败路径添加 `push_status != 'pushed'` guard 防覆盖
- P1-1: GlobalConfig 加载后添加 `target_days > 0` 等正值校验

**Phase 2 — 健壮性：**
- P1-2: `enqueue_task` 递归重试添加深度限制（max 2）
- P1-3: OrderItem 同步改用 UPSERT + 清理旧 items
- P1-7: `parse_purchase_date` 容错（格式错误视为紧急），API 层保持严格校验
- P1-4/P1-5: 同步 overlap 窗口提取为可配置参数
- P1-6: Token 重试添加 0.3-0.7s 随机 jitter
- P1-8: Reaper 日志标注容器实例 ID

**Phase 3 — 工程质量：**
- P2-1: Step4 invariant 触发时添加结构化日志
- P2-4: 在途 90 天 cutoff 添加业务理由注释
- P2-5: `allocation_mode` 零数量语义从 `"matched"` 改为 `"zero_qty"`
- P2-6: zipcode 数值 `=`/`!=` 比较改用整数避免浮点精度
- P2-7: 推送过滤 `total_qty=0` 条目
- P2-8: `api_call_log` 写入失败添加结构化计数字段
- P3-5: `rate_limit._LIMITERS` 添加有界性说明

测试基线：169 passed（原 163 + 新增 6）

### 3.0c 认证模块云交付就绪修复（2026-04-12，云交付评分卡 M6 阶段）

- `backend/app/api/auth.py` 新增 5 类 structlog 业务事件日志（`auth_login_blocked_locked` / `auth_login_failed` / `auth_login_lockout_triggered` / `auth_login_reset_after_success` / `auth_login_success`），消除"认证模块零业务日志"缺口
- `backend/app/api/auth.py:33-41` `_get_login_source_key` 加代码注释明确对 `deploy/Caddyfile` `header_up X-Forwarded-For {remote_host}` 覆盖行为的依赖关系
- `frontend/src/views/LoginView.vue`：
  - 中文化 "Sign in to Restock" → "登录 Restock"，"Sign in" → "登录"
  - 新增 `startLockedCountdown` / `clearLockedCountdown` 消费后端 `LoginLocked.detail.locked_until`，每秒更新"账号已锁定，剩余 X 分 Y 秒"倒计时
- `docs/runbook.md` 新增第 3.4 节"JWT 密钥管理（首次生成 / 轮换 / 泄漏应急）"，约 100 行 SOP；原 3.5-3.8 顺延到 3.5-3.9
- 评分影响：M6 D5 从 2 升 3；M6 平均分 2.56 → 2.67；P0-5（JWT 轮换文档）从 ❌ 未实现升级为 ✅ 已实现；P1-6（XFF 信任源）降级到 P2（Caddy 架构已缓解）

### 3.0a Reaper 容器拓扑冗余（2026-04-11，云交付评分卡 M4 阶段）

- `deploy/docker-compose.yml` 中 scheduler 服务的 `PROCESS_ENABLE_REAPER` 从 `false` 改为 `true`
- Reaper 现在在 worker 和 scheduler 两个容器**冗余运行**，任一容器存活即可回收僵尸任务
- 双 reaper 通过 PostgreSQL 行锁 + 幂等 UPDATE 天然并发安全
- 背景：M4 审计发现"worker+reaper 共容器、backend 关 reaper"的拓扑下若 worker 容器整体 crash 则无进程回收僵尸任务（P1-M4-3）
- `docs/runbook.md` 3.2 节同步更新：检查两个容器的 reaper 日志 + 追加"强制中断 running 任务"的 fallback 说明（因当前无 cooperative cancel 机制）
- `backend/app/models/task_run.py:89` `attempt_count` 字段追加诊断 tripwire 注释

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

- **H4 编辑口径修正**：`total_qty` 与 `country_breakdown` 脱钩，国家补货量不再要求与总采购量一致；正补货量国家缺少 `t_purchase` 时由后端默认当天
- **step3**：返回类型从 `tuple[dict, dict]` 简化为 `dict[str, dict[str, int]]`

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

### 3.14 邮编规则同优先级 tied 均分

- 2026-04-11 — matcher 由 `match_warehouse(...) -> str | None` 重构为 `match_warehouses(...) -> list[str]`：按 `(priority, rule.id)` 排序后返回"首批同 priority 命中"的仓库列表，同 `warehouse_id` 去重。step5 消费端迭代 winners 按 `qty / N` 累加到 `known_counts`（类型由 `int` 改为 `float`；最终整数输出由下游 `round` + 尾仓兜底保证精确）。业务配置方式：把多条规则的 `priority` 填相同值即可触发均分，对任何 operator（`=`/`contains`/`between`…）自动适用。tied 仓中若有不在 `country_warehouses` 列表的，先过滤再按剩余数量均分。

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
