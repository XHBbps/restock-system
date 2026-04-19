# Restock System 项目进度

> 最近更新：2026-04-19（Plan A 前端收尾：导出按钮 + 历史快照区、生成开关卡片、清理赛狐推送时代死代码；业务人员角色补齐 `restock:export` + `config:view`）
> 本文档记录已交付能力和近期重大变更。架构细节见 [`Project_Architecture_Blueprint.md`](Project_Architecture_Blueprint.md)。

---

## 1. 总体状态

| 维度 | 状态 |
|---|---|
| 主链路 | 打通 — 赛狐同步 → 补货计算 → 建议编辑 → Excel 导出 + Snapshot 版本化（Plan A 已替换推送赛狐） |
| 工程化 | 运行时配置校验、健康检查、部署脚本、CI 骨架、测试覆盖已就绪 |
| 前端 | 已统一到 `PageSectionCard`；订单、历史、商品、库存、出库记录等高增长页面已切换为后端分页模式，设计系统对齐 shadcn Zinc |
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
- **本地 dev 全栈验证**：新增 `deploy/docker-compose.dev.yml`、`deploy/Caddyfile.dev`、`deploy/.env.dev.example`，支持本机验证 db → migration → backend/worker/scheduler → frontend → caddy 的完整容器链路，且不污染生产 Compose
- **进程角色解耦**：通过 `PROCESS_ENABLE_WORKER/REAPER/SCHEDULER` 将 backend 镜像拆为 3 个服务
  - `backend` — 仅 HTTP API
  - `worker` — 任务执行 + 僵尸回收
  - `scheduler` — 定时入队
- **资源限制**（`docker-compose.yml`）：db 1G、backend 512M、worker 512M、scheduler 512M、frontend 256M、caddy 128M
- **后端镜像启动修复**：`backend/Dockerfile` 运行阶段将 `/install/lib/python3.11/site-packages` 加入 `PYTHONPATH`，修复 `uvicorn` / `alembic` 在容器中 `ModuleNotFoundError` 的阻塞问题

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
- **信息总览快照刷新任务**：`refresh_dashboard_snapshot` 通过 TaskRun 入队执行；`GET /api/metrics/dashboard` 只读返回现有快照 / 活跃任务状态，手动“刷新快照”是默认触发入口
- **订单详情同步与详情获取**：`sync_order_detail` 当前按 2 QPS / 2 并发保守抓取；订单页提供右侧独立“详情获取”组件，仅提供天数选择与触发按钮；手动触发会优先复用活跃的 `refetch_order_detail`、`sync_order_detail` 或 `sync_all` 任务，避免并发重复抓取，且不再对手动详情获取施加单次数量上限；任务执行中会按“已完成 X / 失败 Y / 总数 N”持续回写精确进度

### 2.3 补货计算引擎

- **6 步流水线**（`backend/app/engine/runner.py`）：
  1. `step1_velocity` — 加权日均销量（7日×0.5 + 14日×0.3 + 30日×0.2）
  2. `step2_sale_days` — 可售天数 + 库存聚合（含在途）
  3. `step3_country_qty` — 各国补货量
  4. `step4_total` — 总采购量（扣减国内库存 + 缓冲天数）
  5. `step5_warehouse_split` — 按邮编规则分配到具体仓库
  6. `step6_timing` — 紧急标志（任一有效国家 `sale_days <= lead_time_days` 即为紧急）
- **补货区域过滤**：全局参数 `restock_regions` 支持按国家多选；为空数组时表示全部国家参与计算，配置后仅这些国家的订单会参与 `step1_velocity` 销量统计和 `step5_warehouse_split` 的国家订单分仓
- **并发保护**：`pg_advisory_xact_lock(7429001)` 事务级锁，阻止并发引擎覆盖彼此
- **快照追溯**：`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot` 存入 JSONB 字段；其中 `global_config_snapshot` 会记录 `restock_regions`

### 2.4 补货建议管理

- **建议单**：`draft/partial/pushed/archived/error` 状态流转
- **跨页选择**：补货发起页的 `selectedIds` 数组跨分页保持，支持全选筛选后的所有条目
- **编辑校验**：建议详情支持编辑 `total_qty` / `country_breakdown` / `warehouse_breakdown`；国家补货量不要求与总采购量一致，已配置仓库时仓内分量之和必须等于国家补货量；`urgent` 会随国家补货量变更按对应 SKU 的提前期重新判定
- **历史记录删除**：历史记录页新增建议单删除入口，允许删除 `draft` / `partial` / `error` / `archived`；`pushed` 建议单保留历史追溯，不允许删除
- **触发方式中文化**：历史记录页“触发方式”由原始值改为中文展示，当前口径统一为“手动触发 / 自动触发”
- **推送到赛狐**：`pushback/purchase.py` 合并选中条目生成采购单，失败自动重试
- **去重**：同一 suggestion 的同一组推送条目同时只有一个 push 任务（`dedupe_key="push_saihu#<id>#<sorted_item_ids>"`）

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
- **数据加载模式**：订单页、历史记录页、商品页、库存页、出库记录页使用“后端分页 + 后端筛选”；仓库、店铺等低增长基础页仍保留轻量分页
- **筛选控件高度统一**：`PageSectionCard` 的 `section-actions` 强制所有控件 32px 高度
- **订单状态中文映射**：`DataOrdersView.vue` 添加 `ORDER_STATUS_LABEL`（已发货 / 部分发货 / 未发货 / 待处理 / 已取消）
- **全局参数页补货区域配置**：`GlobalConfigView.vue` 新增“补货区域”多选，选项复用 `COUNTRY_OPTIONS`，保存前变更检测与配置变更提示已纳入 `restock_regions`
- **信息总览风险图与首行卡片**：`WorkspaceView.vue` 左侧图表使用“各国缺货风险分布”分组柱状图，按实时 `sale_days` 把各国 SKU 分为“紧急 / 临近补货 / 安全”三类并列展示；首行卡片则改为“需补货SKU / 无需补货SKU / 覆盖国家”，其中 `需补货SKU` 基于当前系统补货计算口径统计 `total_qty > 0` 的启用 SKU 数，`无需补货SKU` 为剩余启用 SKU 数，右侧“补货量国家分布”继续基于当前建议单全部条目的 `country_breakdown` 汇总
- **急需补货SKU口径**：信息总览中的“急需补货SKU”按“商品信息 / 国家 / 可售天数”逐行展示；仅展示存在有效国家级 `sale_days` 且低于等于提前期的行；其中可售天数直接取当前建议单 `sale_days_snapshot` 中该国家对应 SKU 的值，小于 1 天统一显示为 `<1天`
- **信息总览快照模式**：`WorkspaceView.vue` 优先读取 `/api/metrics/dashboard` 返回的 `dashboard_snapshot` 缓存，页面头部展示快照状态和同步时间；无缓存或旧快照时返回 `snapshot_status="missing"`，不自动触发刷新，页面仅在具备 `home:refresh` 时展示“刷新快照”按钮与任务进度轮询

### 3.50 Plan A 前端收尾：导出按钮 + 历史快照区 + 生成开关 + 推送死代码清理（2026-04-19）
- 前端：新增快照 API 客户端与 blob 下载工具；建议单详情页加导出按钮（一步式 POST+GET blob）与历史快照区；全局配置页加生成开关卡片（即时保存 + 翻 ON 二次确认）；列表页加开关只读 tag；全量清理赛狐推送时代死代码（~110 行 UI + 8 死字段 + `utils/status.ts` map + 4 个测试文件的推送相关 case）；`Suggestion.status` TS 枚举收敛为 `'draft' | 'archived' | 'error'`；`HistoryView.canDelete` 改用 `snapshot_count === 0`。
- 后端：alembic 迁移 `20260419_0000_grant_export_and_config_view_to_business_role` 给“业务人员”角色补齐 `restock:export` + `config:view`（幂等 `ON CONFLICT DO NOTHING`）。
- 新增/更新文件：`frontend/src/api/snapshot.ts`、`frontend/src/utils/download.ts` 新增；`frontend/src/api/suggestion.ts`、`frontend/src/api/config.ts`、`frontend/src/utils/status.ts`、`frontend/src/views/SuggestionDetailView.vue`、`frontend/src/views/SuggestionListView.vue`、`frontend/src/views/HistoryView.vue`、`frontend/src/views/GlobalConfigView.vue` 同步收敛为导出视角，并清理推送字段 / pushItems / selection 列等相关 UI 与测试分支。

### 3.49 Plan A 后端导出重构：推送赛狐 → Excel 导出 + Snapshot 版本化（2026-04-19）
- 数据模型：`backend/alembic/versions/20260418_0900_redesign_to_export_model.py` 新增 `suggestion_snapshot` / `suggestion_snapshot_item` / `excel_export_log` 三张表，清空 `suggestion` / `suggestion_item` 的推送字段，追加 `export_status` / `exported_snapshot_id` / `exported_at` / `archived_trigger` / `archived_by` 等导出 & 归档审计字段；`suggestion.status` 枚举收缩为 `draft / archived / error`；`global_config` 新增 `suggestion_generation_enabled` 与 `generation_toggle_updated_by / generation_toggle_updated_at`；非生产数据采用一次性迁移。
- ORM + DTO 同步：`backend/app/models/{suggestion,suggestion_snapshot,excel_export_log,global_config}.py`、`backend/app/schemas/{suggestion,suggestion_snapshot,config}.py` 去除全部 push 字段并新增 snapshot 相关 DTO。
- Excel 生成：新增 `backend/app/services/excel_export.py`，基于 openpyxl 生成四 Sheet 工作簿（汇总 / 明细 / 国家 / 仓库分仓）；文件落到 `deploy/data/exports/{yyyy}/{mm}/` 容器卷，文件名由 `build_filename(suggestion_id, version, exported_at_compact)` 统一；`openpyxl>=3.1.2` 加入 `backend/pyproject.toml` 生产依赖。
- 新增快照 API（`backend/app/api/snapshot.py`）：`POST /api/suggestions/{id}/snapshots` 创建并冻结 snapshot、生成 Excel 并将 `suggestion_generation_enabled` 翻为 OFF；`GET /api/suggestions/{id}/snapshots`、`GET /api/snapshots/{id}`、`GET /api/snapshots/{id}/download` 支持列表 / 详情 / 下载计数 + `excel_export_log` 审计；时间戳统一走 `now_beijing()`。
- 生成开关 API（`backend/app/api/config.py`）：新增 `GET/PATCH /api/config/generation-toggle`；翻 ON 时连带归档全部 `status='draft'` 建议单并打上 `archived_trigger='admin_toggle'` + `archived_by` / `archived_at`。
- 建议单 & 引擎清理：`backend/app/api/suggestion.py` 删除 `POST /api/suggestions/{id}/push`，`GET /api/suggestions` 注入 `snapshot_count`，删除接口校验快照归属；`backend/app/engine/runner.py` 在生成开关关闭时直接返回 `None`，`_archive_active` 现由 `run_engine` 在写入新 draft 前主动调用，移除 `commodity_id` 自动补齐；`backend/app/tasks/access.py` 及任务注册清理 `push_saihu`。
- 权限：`backend/app/core/permissions.py` 新增 `restock:export` / `restock:new_cycle`，`superadmin` 自动继承。
- 代码删除：`backend/app/pushback/purchase.py`、`backend/app/saihu/endpoints/purchase_create.py`、`backend/app/core/commodity_id.py` 及对应 `push_saihu` / `test_pushback_*` / `test_commodity_id.py` 等旧单测。
- 集成测试抱真实 PostgreSQL：`backend/tests/integration/conftest.py` 采用 `NullPool` 避免跨 event loop 连接复用，client fixture 预置 role+sys_user 并以 `unittest.mock.patch` 短路 `/readyz` 的数据库 / 后台探测；`backend/tests/integration/factories.py` 新增 `seed_test_user`；`backend/pyproject.toml` 将 `asyncio_default_fixture_loop_scope` 改为 `function`；新增 `backend/tests/integration/test_export_e2e.py`、`test_generation_toggle_api.py` 等，`test_config_api.py` 同步新字段。24 项集成测试在 `replenish_test` 库全绿（`TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5433/replenish_test`）。

### 3.44 鉴权/RBAC 收口与快照刷新边界修复（2026-04-16）
- `backend/app/api/config.py`、`backend/app/api/data.py`、`backend/app/api/suggestion.py` 不再使用弱化版 `get_current_session()`；改为基于 `get_current_user()` / `require_permission()` 的后端权限校验，分别对 `config:*`、`data_base:*`、`data_biz:*`、`sync:view`、`restock:*`、`history:delete` 生效
- `backend/app/api/task.py` 改为按 `job_name` 做作业级权限隔离：同步类任务映射到 `sync:view` / `sync:operate`，`calc_engine` 与 `push_saihu` 映射到 `restock:operate`，`refresh_dashboard_snapshot` 映射到 `home:refresh`；通用创建接口不再接受 `push_saihu`
- `backend/app/api/suggestion.py` 推送去重键改为 `push_saihu#<suggestion_id>#<sorted_item_ids>`，并对 `item_ids` 做排序去重，避免不同推送子集误复用同一活跃任务
- `backend/app/api/metrics.py` 将 `GET /api/metrics/dashboard` 收敛为纯读取接口；无快照或旧快照时返回 `snapshot_status="missing"`，不再自动入队刷新；`GET /api/metrics/prometheus` 新增 `monitor:view` 校验
- `deploy/Caddyfile` 为 `/api/metrics/prometheus` 增加独立内网 matcher，公网请求直接返回 404，作为应用层权限之外的第二道防线
- **测试**：新增 `backend/tests/unit/test_task_api.py`，并更新 `backend/tests/unit/test_metrics_snapshot_api.py`、`backend/tests/unit/test_suggestion_patch.py`、`backend/tests/integration/conftest.py`、`frontend/src/views/__tests__/WorkspaceView.test.ts`

### 3.45 订单页大批量加载性能优化（2026-04-16）
- `backend/app/api/data.py` 的 `GET /api/data/orders` 新增 `shop_id` 过滤参数；订单列表查询改为严格按当前页返回，并仅对当前页订单补查 `item_count` / `has_detail`，避免大批量订单下前端一次加载 5000 条和后端批量补查明细状态
- `backend/app/models/order.py` 与 `backend/alembic/versions/20260416_1700_add_order_page_indexes.py` 为 `order_header` 补充 `shop_id + purchase_date`、`order_status + purchase_date` 索引，优化订单页按店铺/状态倒序浏览
- `frontend/src/views/data/DataOrdersView.vue` 改为服务端分页：页码、页大小、筛选、排序均回传 `/api/data/orders`；SKU 输入改为短防抖搜索；店铺筛选选项改为独立调用 `listDataShops()`，不再从当前页订单数据推导
- **测试**：新增 `backend/tests/unit/test_data_orders_api.py` 与 `frontend/src/views/__tests__/DataOrdersView.test.ts`，覆盖 `shop_id` 过滤、空页短路、服务端分页、页码切换、店铺筛选与 SKU 防抖搜索

### 3.46 Review 风险修复：部署链路、前端容错与限流边界（2026-04-17）
- `.github/workflows/ci.yml` 为 `v*` tag 补充 CI + GHCR 发布触发，`publish` 统一覆盖 `main` / `master` / tag；`.github/workflows/deploy.yml` 与 `deploy/scripts/deploy.sh` 同步收敛为按真实 commit SHA 派生 `IMAGE_TAG=sha-<commit>`，并兼容 branch / tag / detached SHA 部署，修复 `main` 分支和 tag 发布容易拉不到镜像的问题
- `deploy/Caddyfile` 的生产 CSP 将 `img-src` 放行到 `https://m.media-amazon.com`，与赛狐同步的 Amazon 商品主图来源保持一致，避免订单/商品页缩略图被浏览器策略拦截
- `frontend/src/config/appPages.ts` 新增统一页面定义，`frontend/src/router/index.ts` 与 `frontend/src/config/navigation.ts` 改为共同消费同一份路由/菜单元数据，减少页面 path / title / permission 双份维护
- `frontend/src/utils/storage.ts` 新增安全读取工具；`frontend/src/stores/auth.ts`、`frontend/src/stores/sidebar.ts` 在 localStorage JSON 损坏或结构异常时自动清理脏数据并回退默认值，避免 SPA 启动阶段因 `JSON.parse` 直接崩溃
- `backend/app/tasks/access.py` 收敛 TaskRun 作业白名单与查看/操作权限映射，`backend/app/api/task.py` 改为复用统一注册表；保留 `push_saihu` 仅允许通过专用业务入口触发的约束
- `backend/app/core/rate_limit.py` 为进程内限流补充周期性全局过期清理、`max_tracked_clients` 容量上限和最旧客户端驱逐逻辑，降低不同 IP 扫描导致的内存持续膨胀风险
- **测试**：新增 `backend/tests/unit/test_rate_limit_middleware.py`、`frontend/src/stores/__tests__/sidebar.test.ts`，并扩展 `frontend/src/stores/__tests__/auth.test.ts`

### 3.47 剩余大数据页服务端分页迁移（2026-04-17）
- `backend/app/api/suggestion.py` 的 `GET /api/suggestions` 返回补齐 `page` / `page_size`，历史记录页直接消费后端当前页结果，不再在前端对 5000 条建议单做本地筛选分页
- `backend/app/api/data.py` 复用库存筛选逻辑，并新增 `GET /api/data/inventory/warehouse-groups`，按仓库维度返回分页分组、SKU 数、可用/占用库存合计与当前页明细，库存页在保持“按仓库展开”交互的同时避免一次性加载全部库存
- `backend/app/api/data.py` 新增 `GET /api/data/out-record-types`，出库记录页的类型筛选选项改为独立读取；`DataOutRecordsView.vue` 改为将 SKU、仓库单号、国家、类型、在途状态、排序、分页全部下推到 `/api/data/out-records`
- `frontend/src/views/data/DataProductsView.vue`、`DataInventoryView.vue`、`DataOutRecordsView.vue` 与 `frontend/src/views/HistoryView.vue` 均改为后端分页模式：`rows` 仅保存当前页，`total` 来自接口，筛选变化重置第一页，页码/页大小变化触发重新请求
- **测试**：新增 `backend/tests/unit/test_data_inventory_groups_api.py`、`backend/tests/unit/test_suggestion_list_api.py`、`frontend/src/views/__tests__/DataProductsView.test.ts`、`frontend/src/views/__tests__/DataInventoryView.test.ts`，并更新历史记录与出库记录页测试覆盖服务端分页参数

### 3.48 GHCR owner 小写归一化修复（2026-04-17）
- `.github/workflows/ci.yml` 的 `publish` job 新增 owner 归一化步骤，统一使用小写 owner 生成 `ghcr.io/<owner>/restock-{backend,frontend}:sha-<commit>` 与 `latest` 标签，修复 GitHub 用户名包含大写字符时 buildx 直接报 `repository name must be lowercase`
- `deploy/scripts/validate_env.sh` 将 `GHCR_OWNER` 纳入必填校验，并显式拒绝非小写值；`deploy/scripts/deploy.sh` 在调用 Compose 前再次导出小写 `GHCR_OWNER`，避免线上 `.env` 沿用旧值导致拉镜像失败
- `deploy/.env.example` 与 `docs/deployment.md` 同步明确 `GHCR_OWNER` 必须使用全小写 GitHub 用户名/组织名
- `.github/workflows/deploy.yml` 的 `check-ci` job 补充 `contents: read`，修复手动触发部署时 `actions/checkout` 因权限不足报 `repository not found` 的阻塞问题

### 3.43 CI 安全校验修复：JWT 密钥长度 + 前端依赖审计（2026-04-15）
- `backend/app/config.py` 将默认 `jwt_secret` 占位值提升到 32 字节以上，并在 `validate_settings()` 中新增 `JWT_SECRET must be at least 32 bytes` 校验；生产环境占位值检测同步更新，避免 `PyJWT` 因 HMAC 密钥过短抛出 `InsecureKeyLengthWarning`，导致 `tests/unit/test_security.py` 在 CI 中失败
- `frontend/package.json`、`frontend/package-lock.json` 升级 `axios` 至 `1.15.0`、`vitest` / `@vitest/coverage-v8` 至 `4.1.4`，并通过同一依赖树消除 GitHub Actions 中 `npm audit --audit-level=high` 的高危告警
- **验证**：`backend/tests/unit/test_security.py` 10 项单测已通过；前端在 Docker `node:20-alpine` 环境完成 `npm run build`、`npm run test:coverage`、`npm audit --audit-level=high`，结果为 `found 0 vulnerabilities`

### 3.42 前端 CI 等价校验改为 Node 20 容器链路（2026-04-15）

- 新增 `scripts/frontend-check.ps1` 与 `scripts/frontend-check.sh`，统一使用 Docker `node:20-alpine` 执行 `npm ci && npm run build && npm run test:coverage`
- 前端依赖安装写入 Docker volume（`restock-frontend-check-node-modules`、`restock-frontend-check-npm-cache`），避免污染宿主机 `frontend/node_modules`
- `scripts/check.ps1` 与 `scripts/check.sh` 的前端部分改为默认调用上述容器脚本；后端校验仍保持宿主机 Python 原生执行
- `docs/onboarding.md` 同步区分“本机开发通道”和“CI 等价校验通道”，明确本机 Node 可继续用于 `npm run dev`，但关键校验不再依赖宿主机版本
- **验证**：Node 20 容器内前端 `build` 与 `test:coverage` 已通过，消除 Windows + 非 CI Node 版本导致的本地噪音失败

### 3.41 后端镜像依赖路径修复 + 本地 dev 全栈容器验证（2026-04-15）

- `backend/Dockerfile` 运行阶段补充 `PYTHONPATH=/app:/install/lib/python3.11/site-packages`，修复使用 `pip install --prefix=/install` 后 `uvicorn`、`alembic` 启动脚本可执行但模块无法 import 的问题
- `deploy/docker-compose.dev.yml` 新增独立的本地 dev 全栈 6 服务编排：db 暴露 `5433`、Caddy 暴露 `8088`，数据目录使用 `deploy/data/pg-dev` 与 `deploy/data/caddy-dev`
- `deploy/docker-compose.dev.yml` 与 `deploy/docker-compose.yml` 为全部服务增加固定 `container_name`，本地容器统一为 `restock-dev-*`，生产容器统一为 `restock-*`
- `deploy/Caddyfile.dev` 新增本地 HTTP 反代入口，统一代理 `/api/*`、`/docs*`、`/openapi.json`、`/healthz`、`/readyz` 和前端静态页面
- `backend/alembic/versions/20260410_1300_extend_zipcode_rule_operator.py` 与 `backend/alembic/versions/20260411_1500_zipcode_rule_between_operator.py` 兼容删除历史命名约定叠加产生的 `ck_zipcode_rule_ck_zipcode_rule_operator_enum`，修复全新数据库从零迁移失败
- `deploy/docker-compose.yml` 与 `deploy/docker-compose.dev.yml` 将前端健康检查改为 `127.0.0.1:8080`，修复 Alpine `wget` 对 `localhost` 走 IPv6 时的假失败
- `deploy/.env.dev.example`、`docs/deployment.md`、`docs/onboarding.md` 同步补充本地 dev 全栈启动说明，保持生产部署入口与本地验证入口分离
- **验证**：已完成 Compose 构建、后端镜像依赖导入校验、本地全栈迁移与健康检查链路验证

### 3.40 项目审查修复（2026-04-15）

批量修复审查发现的 40 项问题，涵盖 5 个批次：
- **阻塞级**：通用 500 处理器（防堆栈泄露）、shutdown 资源释放（DB 引擎 + SaihuClient）、ORM 唯一约束对齐、部署脚本修复（rollback detached HEAD、restore_db 清库）
- **性能**：GET 端点只读会话（`db_session_readonly`）、Element Plus unplugin 基础设施、登录页 DOM 精简（2800→1200）、hasChanges 结构化比较、同步任务每 500 条周期性 commit、库存快照 90 天保留策略
- **安全**：trusted proxy 验证（rate_limit + auth）、前端容器非 root（nginx 8080）、Caddyfile 健康端点内网限制 + 请求体限制
- **健壮性**：InTransitRecord FK ondelete=SET NULL、迁移脚本文件锁
- **代码质量**：`_mapUserInfo` 运行时类型校验、AppLayout 移除 `as any`、engine API 类型化封装、401 延迟 import 避免循环依赖、Vitest 覆盖率阈值、Python 依赖 lockfile
- **部署**：容器日志轮转、CPU 限制、滚动重启、PostgreSQL 调优（-c 参数）、前端 healthcheck、备份验证
- **CI/CD**：部署工作流 CI 门控 + 并发控制 + 通知、Docker 镜像构建测试
- **监控**：`GET /api/metrics/prometheus` 基础指标端点（队列深度 + 存活），需要登录且具备 `monitor:view`；Caddy 仅对内网来源放行

### 3.38 信息总览快照缓存与 SKU+国家风险口径统一（2026-04-14）
- `backend/app/models/dashboard_snapshot.py` 与 `backend/alembic/versions/20260414_2300_add_dashboard_snapshot.py` 新增 `dashboard_snapshot` 单例缓存表，存储信息总览 payload、刷新状态、开始/完成时间和最近一次错误
- `backend/app/tasks/jobs/dashboard_snapshot.py` 新增 `refresh_dashboard_snapshot` 任务；`backend/app/api/task.py`、`backend/app/main.py` 完成任务注册，信息总览快照改由后台任务生成并写回缓存
- `backend/app/api/metrics.py` 新增 `build_dashboard_payload()`，把首行风险卡片、左侧“各国缺货风险分布”和“急需补货SKU”统一为 SKU+国家口径的实时计算结果；`GET /api/metrics/dashboard` 改为优先返回缓存快照与当前任务状态，缺少缓存时返回 `missing`，由 `POST /api/metrics/dashboard/refresh` 手动入队刷新
- `frontend/src/api/dashboard.ts`、`frontend/src/views/WorkspaceView.vue` 接入快照状态字段、刷新按钮和 `TaskProgress` 轮询；首行卡片文案同步改为“紧急国家商品 / 临近补货国家商品 / 安全国家商品 / 覆盖国家”，右侧“补货量国家分布”继续保持基于当前建议补货单
- **测试**：新增 `backend/tests/unit/test_metrics_snapshot_api.py`、`backend/tests/unit/test_dashboard_snapshot_job.py`，并更新 `backend/tests/unit/test_metrics_dashboard.py`、`frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖快照回读、无缓存自动入队、任务写回和前端刷新交互
- **经验沉淀**：信息总览这类高聚合页面应优先消费快照，以换取稳定口径、可追踪刷新链路和更低的重复计算成本

### 3.39 信息总览首行卡片切换为补货视角（2026-04-14）
- `backend/app/api/metrics.py` 在 `DashboardOverviewPayload` 中新增 `restock_sku_count`、`no_restock_sku_count`，并在 `build_dashboard_payload()` 中直接复用 `step3_country_qty + step4_total` 的现行规则统计“需补货SKU / 无需补货SKU”；当 `GET /api/metrics/dashboard` 读取到缺少新字段的旧 `dashboard_snapshot.payload` 时，接口保留默认值并返回 `missing`，由手动刷新任务修复快照
- `frontend/src/api/dashboard.ts`、`frontend/src/views/WorkspaceView.vue` 将首行卡片改为“需补货SKU / 无需补货SKU / 覆盖国家”，并移除旧的风险说明文案；下方“各国缺货风险分布”“急需补货SKU”“补货量国家分布”保持原有展示逻辑不变
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py`、`backend/tests/unit/test_metrics_snapshot_api.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖新字段返回、旧快照兼容刷新和新卡片文案渲染

### 2.6 数据管理

- **仓库国家变更级联**：修改 `warehouse.country` 时同步更新 `inventory_snapshot_latest` 对应记录，无需等下次同步
- **仓库国家支持清除**：下拉框加 `clearable`，后端 schema 支持 `null`
- **数据页 page_size 上限放宽**：所有 `/api/data/*` 端点的 `le=5000`（原 200），支持一次拉全量
- **建议单列表 page_size 上限**：`/api/suggestions` 的 `le=5000`
- **筛选项统一**：店铺/仓库/订单/库存/出库/补货发起 7 个页面的筛选项布局和高度一致
- **出库页**：原“其他出库（在途观测）”改名为“出库”；主表展示出库单id、出库仓库id、目标国家、更新时间、同步时间、出库单类型、状态，明细按“商品SKU、商品ID、可用数、采购单价”顺序展示；同步时间复用 `lastSeenAt`，状态统一按 `is_in_transit` 映射为“在途 / 完结”，并支持按“出库单类型”单选筛选
- **在途国家识别**：`sync_out_records` 不再使用 `targetFbaWarehouseId -> warehouse.country` 反推国家，而是从备注文本提取国家名（如 `20260410美国-赢捷-加州-散货-在途中` → `US`）；无法识别时保持空值
- **出库目标国家回填**：`sync_out_records` 在正常同步赛狐出库记录后，会顺带扫描历史 `target_country` 为空且备注可识别国家的出库记录，按备注规则补回目标国家，不覆盖已有值

### 2.7 任务队列系统

- **`task_run` 表**：dedupe_key 去重（partial unique index）、priority 调度、lease 心跳
- **Worker** 2 秒轮询 + 30 秒心跳 + 2 分钟租约
- **Reaper** 60 秒扫描过期任务
- **任务进度实时写入**：`current_step` / `step_detail` / `total_steps`，前端 `TaskProgress` 轮询展示；订单详情任务按条数精确展示，店铺/仓库/商品/库存/订单/出库等分页同步任务按赛狐返回 `totalPage` 展示页级百分比，不额外增加预扫描请求
- **SKIPPED 状态**：调度器尝试重复入队活跃任务时创建审计记录

### 2.8 认证与安全

- **JWT HS256**：24 小时有效，单用户 `sub="owner"`
- **登录锁定按 IP 隔离**：从全局共享改为来源 IP 粒度，优先读 `X-Forwarded-For`/`X-Real-IP`
- **新增表**：`login_attempt`（迁移 `20260409_1710_add_login_attempt.py`）
- **API 调用日志**：每次赛狐调用都写 `api_call_log`
- **角色配置页**：`RoleConfigView.vue` — 角色 CRUD + 权限矩阵编辑（按 `group_name` 分组，支持全选/反选），超管角色权限只读展示

---

## 3. 近期重大变更（2026-04-10 ~ 2026-04-15）
### 3.37 急需补货SKU过滤缺失可售天数并统一 `<1天` 展示（2026-04-14）
- `backend/app/engine/step6_timing.py` 将缺失或无效的 `sale_days` 从 urgent 判定中排除，仅对存在且可解析的国家级 `sale_days` 执行 `<= lead_time_days` 判断
- `backend/app/api/metrics.py` 调整 dashboard 的 `top_urgent_skus` 过滤逻辑，缺失 `sale_days` 的国家不再进入“急需补货SKU”列表
- `frontend/src/views/WorkspaceView.vue` 将信息总览中的国家级可售天数展示改为：缺失显示 `-`，小于 1 天统一显示 `<1天`
- **测试**：更新 `backend/tests/unit/test_engine_step6.py`、`backend/tests/unit/test_suggestion_patch.py`、`backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖缺失值忽略、patch 重算和 `<1天` 展示

### 3.36 信息总览急需补货SKU按国家拆行（2026-04-14）
- `backend/app/api/metrics.py` 将 `top_urgent_skus` 从“每个 urgent SKU 一行”改为“每个 urgent SKU 的每个急需国家一行”，返回字段调整为 `commodity_sku / commodity_name / main_image / country / sale_days`
- `frontend/src/views/WorkspaceView.vue` 将“急需补货SKU”列表表头改为“商品信息 / 国家 / 可售天数”，同一 SKU 可出现多行；可售天数直接展示对应国家的 `sale_days`
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖多国家拆行、国家级可售天数和前端列表渲染

### 3.35 出库目标国家历史回填并入同步流程（2026-04-14）
- `backend/app/sync/out_records.py` 将历史 `target_country` 空值回填并入 `sync_out_records` 主流程；每次同步完赛狐出库记录后，都会复用同一套备注解析逻辑补齐历史空值行，但不覆盖已有目标国家
- `backend/app/api/sync.py`、`backend/app/api/task.py` 与 `frontend/src/config/sync.ts` 清理独立的“回填出库目标国家”任务入口，前端仍只保留“出库记录同步”按钮
- **测试**：更新 `backend/tests/unit/test_sync_out_records_job.py` 与 `backend/tests/unit/test_scheduler_api.py`，覆盖回填 helper 和主同步流程内执行回填的行为

### 3.34 出库页补充目标国家列与类型单选筛选（2026-04-14）
- `backend/app/api/data.py` 为 `GET /api/data/out-records` 新增 `type_name` 查询参数，允许按出库单类型精确筛选；`backend/tests/unit/test_data_out_records_api.py` 补充对应参数签名与过滤口径断言
- `frontend/src/api/data.ts`、`frontend/src/views/data/DataOutRecordsView.vue` 在现有风格下新增“出库单类型”单选筛选，主表列顺序调整为“出库单ID / 出库仓库ID / 目标国家 / 更新时间 / 同步时间 / 出库单类型 / 状态”，其中“目标国家”直接展示已有 `targetCountry`
- **测试**：更新 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖目标国家列渲染、出库单类型筛选选择/清空，以及新的列顺序

### 3.33 废弃采购日期字段兼容层清理（2026-04-14）
- `backend/app/engine/runner.py` 移除为旧库保留的 `suggestion_item.t_purchase` / `push_attempt_count` 等动态补默认与运行时表结构探测，建议单条目改为直接按当前 ORM schema 写入；运行引擎前需要确保环境已执行 `alembic upgrade head`
- `backend/tests/unit/test_engine_runner.py` 删除围绕旧表结构兼容写入的回归测试，仅保留当前 schema 行为与 `restock_regions` 透传校验

### 3.32 采购日期移除与紧急规则、在途国家口径调整（2026-04-14）
- `backend/app/engine/step6_timing.py` 移除采购日期计算，`urgent` 统一改为“任一正补货国家的 `sale_days <= lead_time_days`”；`backend/app/engine/runner.py` 不再写入 `suggestion_item.t_purchase`，并新增 `target_days >= lead_time_days` 的运行期保护
- `backend/app/api/suggestion.py`、`backend/app/models/suggestion.py`、`backend/app/schemas/suggestion.py` 与 `frontend/src/views/SuggestionDetailView.vue`、`frontend/src/api/suggestion.ts` 一并移除采购日期字段的存储、接口和前端编辑展示；新增迁移 `backend/alembic/versions/20260414_2100_drop_suggestion_item_t_purchase.py`
- `backend/app/schemas/config.py`、`backend/app/api/config.py` 与 `frontend/src/views/GlobalConfigView.vue` 增加“目标库存天数不能小于采购提前期”的前后端双重校验
- `backend/app/sync/out_records.py` 将在途记录国家改为从备注提取，解析失败时不再回退到仓库国家；补充对应单元测试
- **测试**：新增/更新 `backend/tests/unit/test_engine_step6.py`、`backend/tests/unit/test_suggestion_patch.py`、`backend/tests/unit/test_sync_out_records_job.py`、`backend/tests/unit/test_config_schema.py`、`backend/tests/integration/test_config_api.py`、`frontend/src/views/__tests__/GlobalConfigView.test.ts`、`frontend/src/views/__tests__/SuggestionDetailView.test.ts`、`frontend/src/views/__tests__/SuggestionListView.test.ts`

### 3.31 信息总览图例换行与风险图显示修复（2026-04-13）
- `frontend/src/components/dashboard/DashboardChartCard.vue` 将图表撑满高度的样式约束收敛到“存在 footer 的卡片”场景，避免普通图表卡片被错误压缩，恢复“各国缺货风险分布”正常显示
- `frontend/src/views/WorkspaceView.vue` 将“补货量国家分布”底部图例改为固定四列居中布局，按每行 4 个国家换行；窄屏下按现有响应式规则降为 3 列 / 2 列，保持整体居中
- **测试**：更新 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖国家图例四列居中布局以及 `DashboardChartCard` 的 footer 专用高度约束

### 3.30 信息总览国家分布图例布局优化（2026-04-13）
- `frontend/src/components/dashboard/DashboardChartCard.vue` 支持图表区下方附加自定义 footer 区域；当存在 footer 时，卡片内容按约 2:1 的纵向比例分配给图表和底部补充信息区
- `frontend/src/views/WorkspaceView.vue` 将“补货量国家分布”从 ECharts 内置 legend 调整为卡片底部自定义图例，环形图稳定展示在上部约 2/3 区域，底部图例位于下部约 1/3 区域并支持自动换行
- **测试**：更新 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖国家分布图关闭内置 legend、渲染底部自定义图例和相关布局约束

### 3.29 信息总览安全 SKU 口径与列表布局优化（2026-04-13）
- `backend/app/api/metrics.py` 调整 dashboard overview 首行风险卡片口径：`urgent_count`、`warning_count`、`safe_count` 改为基于全部启用 SKU 的最小可售天数统计，其中 `< lead_time_days` 记为“紧急”，`>= lead_time_days 且 < target_days` 记为“临近补货”，`>= target_days` 记为“安全”；下方“各国缺货风险分布”“补货量国家分布”仍保持基于当前最新 `draft/partial` 建议单
- `frontend/src/views/WorkspaceView.vue` 同步更新首行卡片提示文案，明确说明风险卡片统计对象为“全部启用 SKU”；同时移除“急需补货 SKU”卡片的固定高度，改为与右侧“补货概览”卡片等高拉伸，滚动区域占满可用内容区
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖全部启用 SKU 风险分桶口径和急需列表拉伸布局

### 3.28 建议单商品ID自动补齐与推送状态口径修复（2026-04-13）
- `backend/app/core/commodity_id.py` 新增 SKU -> `commodity_id` 解析与建议条目推送可用性修复逻辑，按 `commodity_sku` / `seller_sku` 分层回退匹配；`backend/app/engine/runner.py` 复用该解析逻辑，生成建议单时尽量直接补齐 `commodity_id`
- `backend/app/api/suggestion.py` 在读取当前建议单/建议单详情以及手动推送前，自动为缺少 `commodity_id` 的条目重新解析并修复 `push_blocker`、`push_status`；已能补齐商品ID的旧条目刷新后会恢复为可推送
- `frontend/src/views/SuggestionListView.vue` 恢复推送状态真实语义：仅真正可推送条目显示为“待推送”并允许勾选，`blocked` 改为“待处理”独立筛选；`frontend/src/utils/status.ts` 同步状态标签文案
- **测试**：新增 `backend/tests/unit/test_commodity_id.py`，并更新 `backend/tests/unit/test_engine_runner.py`、`backend/tests/unit/test_suggestion_patch.py`、`frontend/src/views/__tests__/SuggestionListView.test.ts`、`frontend/src/utils/status.test.ts`

### 3.27 补货发起页推送标签口径收敛（2026-04-13）
- `frontend/src/views/SuggestionListView.vue` 移除商品信息卡片后的推送阻塞标签展示，并将 `blocked` 条目在前端筛选与排序口径中并入“待推送”
- `frontend/src/utils/status.ts` 将建议条目 `push_status='blocked'` 的展示文案统一为“待推送”，不再向用户暴露“不可推送”标签
- **测试**：新增 `frontend/src/views/__tests__/SuggestionListView.test.ts`，并更新 `frontend/src/utils/status.test.ts`，覆盖 blocked 并入待推送和商品信息区不再传递 blocker 标签

### 3.26 出库页筛选默认值与清空交互修正（2026-04-13）
- `frontend/src/views/data/DataOutRecordsView.vue` 将“状态”筛选默认值从“在途”改为“未筛选”，并为“状态”“国家”两个下拉补齐清空后立即重载列表的交互
- `backend/app/api/data.py` 将 `GET /api/data/out-records` 的 `is_in_transit` 查询参数默认值改为 `None`，使未传参时返回全部出库记录而不是仅返回在途记录
- **测试**：更新 `frontend/src/views/__tests__/DataOutRecordsView.test.ts` 与 `backend/tests/unit/test_data_out_records_api.py`，覆盖默认无状态筛选、状态清空和国家清空场景

### 3.25 历史记录删除与触发方式中文化（2026-04-13）
- `backend/app/api/suggestion.py` 新增 `DELETE /api/suggestions/{id}`，按建议单维度物理删除 `suggestion` 及级联明细；仅 `draft` / `partial` / `error` / `archived` 允许删除，`pushed` 返回冲突错误
- `frontend/src/api/suggestion.ts` 新增 `deleteSuggestion()`；`frontend/src/views/HistoryView.vue` 将筛选顺序调整为“SKU关键字 → 日期筛选 → 状态筛选”，操作列新增红色“删除”，确认框使用项目现有 MessageBox 风格并补充危险操作文案
- 历史记录页“触发方式”改为中文展示：`manual` 显示“手动触发”，`scheduler` 显示“自动触发”，未知值兜底显示原始文本
- **测试**：新增 `frontend/src/views/__tests__/HistoryView.test.ts`，并扩展 `backend/tests/unit/test_suggestion_patch.py` 覆盖删除接口允许/拒绝场景

### 3.24 同步时间展示统一（2026-04-13）
- `frontend/src/utils/format.ts` 将 `formatUpdateTime` 统一为 `YYYY-MM-DD HH:mm`，用于数据页“同步时间”和出库页“更新时间/同步时间”展示；对应 `frontend/src/utils/format.test.ts` 同步更新断言
- `frontend/src/views/data/DataProductsView.vue`、`DataShopsView.vue`、`DataWarehousesView.vue`、`DataInventoryView.vue` 将列表列名从“更新时间”统一调整为“同步时间”，保持原有页面结构和视觉样式不变
- `frontend/src/views/data/DataOutRecordsView.vue` 保留主表“更新时间”，新增基于 `lastSeenAt` 的“同步时间”列，并重新分配主表列宽，使长字段更宽、短字段更紧凑
- **测试**：更新 `frontend/src/views/__tests__/DataTimeLabels.test.ts` 与 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖统一命名和出库记录双时间列渲染

### 3.23 信息总览图表与风险卡片口径调整（2026-04-13）
- `backend/app/api/metrics.py` 为 dashboard overview 新增 `warning_count`、`safe_count`、`risk_country_count` 和 `country_restock_distribution`，其中右侧“补货量国家分布”改为汇总当前最新 `draft/partial` 建议单全部条目的 `country_breakdown`
- `frontend/src/api/dashboard.ts` 同步扩展 `DashboardOverview` 类型；`frontend/src/views/WorkspaceView.vue` 将首行卡片改为“紧急 SKU / 临近补货 / 安全 SKU / 覆盖国家”，左侧风险图从堆叠柱状图调整为分组柱状图
- 右侧“补货量国家分布”继续保留饼图样式，但数据源不再限制为前 10 个紧急 SKU，因此当前建议单中存在补货量的国家都会参与展示
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖新增汇总字段、当前建议单国家补货量分布和前端图表/卡片渲染

### 3.22 信息总览改为各国缺货风险分布（2026-04-13）
- `backend/app/api/metrics.py` 将 dashboard overview 从“各国平均可售天数”调整为“各国缺货风险分布”，按当前最新 `draft/partial` 建议单的 `sale_days_snapshot` 基于全局 `lead_time_days`、`target_days` 分桶，返回各国 `urgent_count` / `warning_count` / `safe_count`
- `frontend/src/api/dashboard.ts` 同步更新 `DashboardOverview` 类型，新增 `lead_time_days` 和 `country_risk_distribution`，移除旧的 `country_stock_days` 口径
- `frontend/src/views/WorkspaceView.vue` 左侧图表替换为风险分布图，tooltip 明确展示“紧急 / 临近补货 / 安全”数量及全局阈值；右侧“补货量国家分布”饼图继续保留
- **测试**：新增 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖风险分桶、dashboard 返回结构和前端图表渲染

### 3.21 补货区域接入全局参数与引擎过滤（2026-04-13）
- `backend/app/models/global_config.py`、`backend/alembic/versions/20260414_1500_add_restock_regions_to_global_config.py` 为 `global_config` 新增 `restock_regions` JSONB 字段，默认值为 `[]`；`backend/app/main.py` 启动初始化时同步补齐默认配置
- `backend/app/core/restock_regions.py` 统一处理补货区域的规范化与可用国家集合解析；`backend/app/schemas/config.py` 复用该逻辑，对输入执行去空、去重、转大写和 2 位国家码校验
- `backend/app/engine/runner.py` 在生成建议前解析 `restock_regions`，并把允许国家集合传入 `step1_velocity` 与 `step5_warehouse_split`；`restock_regions=[]` 明确表示“全部国家参与计算”
- `backend/app/engine/runner.py` 写入的 `global_config_snapshot` 新增 `restock_regions`；历史建议不回填，仅后续新生成建议携带该快照
- `frontend/src/views/GlobalConfigView.vue` 保持原有 `PageSectionCard + el-form` 风格，在全局参数页新增“补货区域”多选控件；保存 payload、未保存变更检测和“建议重新生成补货建议单”提示均已覆盖该字段
- **测试**：新增/更新 `backend/tests/unit/test_config_schema.py`、`backend/tests/unit/test_engine_step1.py`、`backend/tests/unit/test_engine_step5.py`、`backend/tests/unit/test_engine_runner.py`、`backend/tests/integration/test_config_api.py`、`frontend/src/views/__tests__/GlobalConfigView.test.ts`，覆盖参数校验、SQL 过滤、引擎透传与前端交互

### 3.20 同步任务进度可观测增强（2026-04-13）
- `backend/app/sync/order_detail.py` 将 `sync_order_detail` / `refetch_order_detail` 的进度文案统一为“已完成 X / 失败 Y / 总数 N”，按当前目标集合精确回写，不增加额外赛狐请求
- `backend/app/saihu/endpoints/shop.py`、`warehouse.py`、`product_listing.py`、`inventory.py`、`order_list.py`、`out_records.py` 为分页迭代器补充页元信息回调；对应 `sync_*` 任务在不额外预扫的前提下，直接复用赛狐返回的 `totalPage` 输出“第 P / N 页”进度
- `frontend/src/components/TaskProgress.vue` 新增对“按条数”和“按页数/步骤”两类进度文案的解析，可在已有任务轮询接口上直接展示确定型百分比，无法解析时仍回退为不确定进度条
- **测试**：补充 `backend/tests/unit/test_sync_order_detail_job.py`、`backend/tests/unit/test_sync_product_listing_job.py`、`backend/tests/unit/test_sync_order_list.py` 与 `frontend/src/components/TaskProgress.test.ts`，覆盖精确进度、分页进度与前端回退逻辑

### 3.19 出库记录字段补齐（2026-04-13）
- `backend/app/sync/out_records.py` 在同步赛狐其他出库记录时，额外落库 `warehouseId`、`updateTime`、`type`、`typeName`，并为明细落库 `commodityId`、`perPurchase`
- `backend/alembic/versions/20260414_1300_extend_in_transit_out_record_fields.py` 为 `in_transit_record` / `in_transit_item` 补齐上述展示字段，支撑数据页直接展示源字段含义
- `backend/app/api/data.py`、`backend/app/schemas/data.py` 与 `frontend/src/api/data.ts` 补齐对应 DTO；出库记录列表默认按 `updateTime desc` 返回，并支持按出库仓库id、更新时间、出库单类型排序
- `frontend/src/views/data/DataOutRecordsView.vue` 将页面标题改为“出库”，主表和明细表按最新业务口径展示字段，状态标签统一为“在途 / 完结”
- **测试**：补充 `backend/tests/unit/test_sync_out_records_job.py`、`backend/tests/unit/test_data_out_records_api.py` 与 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖同步落库、列表排序和页面默认请求/字段渲染

### 3.18 订单详情条件批量获取（2026-04-13）

- `backend/app/api/sync.py` 的 `POST /api/sync/order-detail/refetch` 改为订单详情抓取统一入口：若存在活跃的 `refetch_order_detail`、`sync_order_detail` 或 `sync_all`，则直接返回现有任务供前端复用进度；否则再按回溯天数筛选“订单主表已存在但本地缺少详情”的全部订单并创建后台任务，不再做 500 条截断
- `backend/app/sync/order_detail.py` 的 `refetch_order_detail` 继续绕过 `order_detail_fetch_log` 的已记录过滤，直接消费接口层筛出的订单集合，但仍复用现有详情抓取、失败分类、限流与落库逻辑
- `frontend/src/components/sync/OrderDetailFetchAction.vue` 将订单页入口封装为右侧独立“详情获取”组件；`frontend/src/views/data/DataOrdersView.vue` 只负责承接任务进度和列表刷新
- **测试**：补充 `backend/tests/unit/test_scheduler_api.py`、`frontend/src/components/sync/OrderDetailFetchAction.test.ts` 与 `frontend/src/api/__tests__/sync.test.ts`，覆盖活跃任务复用、详情获取入口提示、手工触发 payload、空命中不建任务与取消手动数量上限后的全量入队

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

- **全局参数**保存后：若 `target_days` / `buffer_days` / `lead_time_days` / `restock_regions` 任一变更，前端警告"建议重新生成补货建议单"
- **仓库国家**修改后：前端警告 + 同步更新库存表
- **邮编规则**变更：不加提示（仅影响仓库分配展示，不影响采购量）

### 3.6 UX 改进

- Checkbox 勾选标记改用 SVG background-image 精确居中
- Tooltip 淡出动画 300ms → 100ms，避免快速移动时堆叠
- 筛选项高度统一 32px
- 全选跨页保持 + 推送上限放宽（原 50 条上限已移除）
- 表格排序图标列宽修复

### 3.7 引擎逻辑修复

- **H4 编辑口径修正**：`total_qty` 与 `country_breakdown` 脱钩，国家补货量不再要求与总采购量一致
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

- `cd backend && .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider`：**213 passed, 8 skipped**
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

- `cd frontend && cmd /c npx vue-tsc --noEmit`：类型检查通过
- `cd frontend && cmd /c npm run test`：Vitest 通过
- `cd frontend && powershell -Command "cmd /c npm run build"`：构建成功

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
