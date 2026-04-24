# Restock System 架构蓝图

> 生成时间：2026-04-11
> 代码库版本：`001-saihu-replenishment` 分支
> 文档目的：定义架构基线，供新增功能和重构时保持一致性

---

## 1. 架构概览

**Restock System** 是一套跨境电商海外仓补货管理系统，采用**分层单体架构（Layered Monolith）**，后端围绕领域业务（补货计算）组织代码，前端采用标准 Vue SPA 结构。

### 核心设计原则

1. **纯异步 I/O**：后端从 Web 层（FastAPI）到数据库层（asyncpg）全链路 async/await，避免阻塞
2. **数据库即队列**：自研 TaskRun 表替代 Celery/Redis，减少部署复杂度
3. **进程内编排**：Worker、Scheduler、Reaper 与 FastAPI 在同一 Python 进程中运行（可通过环境变量分离）
4. **快照即历史**：补货建议生成时快照输入（velocity、sale_days、配置，含 `restock_regions`），已生成的建议单不会因配置变更而改动
5. **批量优先于迭代**：引擎和同步层尽量批量加载，避免 N+1 查询
6. **高增长列表服务端分页**：订单、历史、商品、库存、出库记录等数据量持续增长的页面统一采用后端分页 / 筛选 / 排序，避免单页数据量放大拖慢接口和交互

### 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3.5 / TypeScript 5.7 / Pinia 2 / Vue Router 4 / Element Plus 2.9 / Vite 6 / Vitest 4 / ECharts 6 |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Pydantic 2 / APScheduler / httpx / structlog |
| 数据库 | PostgreSQL 16（asyncpg 驱动）/ Alembic 迁移 |
| 部署 | Docker Compose / Caddy 反向代理 / Nginx 静态托管 |

---

## 2. 系统分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Frontend (Vue 3 SPA)                          │
│  views → components → stores (Pinia) → api client (Axios)          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP + JWT
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                             │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ API Layer (app/api)                                           │ │
│  │ REST 端点: auth / data / suggestion / sync / config / monitor │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Schema Layer (app/schemas) — Pydantic DTO                     │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Business Layer                                                │ │
│  │ ┌───────────┬────────────┬─────────────┬──────────────────┐ │ │
│  │ │ engine/   │ sync/      │ services/   │ tasks/           │ │ │
│  │ │ 6 步计算  │ 赛狐数据同步│ Excel 导出  │ 队列+调度+worker │ │ │
│  │ └───────────┴────────────┴─────────────┴──────────────────┘ │ │
│  │ （已移除 pushback/、saihu/endpoints/purchase_create.py、   │ │
│  │   core/commodity_id.py；见 §3.6 导出快照子系统）            │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Integration Layer (app/saihu) — 赛狐 HTTP 客户端              │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Model Layer (app/models) — SQLAlchemy ORM                     │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ DB Layer (app/db) — AsyncSession Factory                      │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Core (app/core) — logging / exceptions / security / timezone │ │
│  └───────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ async SQL
                               ▼
                     ┌─────────────────────┐
                     │  PostgreSQL 16      │
                     │  20+ tables         │
                     │  (业务 + 队列 + 日志)│
                     └─────────────────────┘
                               ▲
                               │ sync_*
                               │
                     ┌─────────────────────┐
                     │  Sellfox (赛狐 API) │
                     │  店铺/商品/订单/库存 │
                     └─────────────────────┘
```

**依赖方向**：自上而下，下层不反向依赖上层。跨层通信通过 Pydantic DTO（API ↔ 业务）和 ORM 对象（业务 ↔ DB）。

---

## 3. 后端核心组件

### 3.1 补货计算引擎（app/engine）

**职责**：从同步后的订单、库存、在途、商品和仓库数据中，计算一张 `draft` 建议单，同时产出采购视角（SKU 级采购数量）与补货视角（SKU × 国家 × 仓库补货量）。引擎 step 只做纯数据库读取与计算，不调用赛狐 API。

**6 步流水线**：

| Step | 文件 | 输入 | 输出 | 规则 |
|---|---|---|---|---|
| 1 | `step1_velocity.py` | 近 30 天订单 | `velocity[sku][country]` | 加权日均销量：7日×0.5 + 14日×0.3 + 30日×0.2；若 `global_config.restock_regions` 非空，仅这些国家参与补货国家维度计算 |
| 2 | `step2_sale_days.py` | 库存 + 在途 + velocity | `sale_days[sku][country]` | `(available + in_transit) / velocity`；velocity≤0 跳过 |
| 3 | `step3_country_qty.py` | sale_days + target_days | `country_qty[sku][country]` | `max(0, ceil((target_days - sale_days) × velocity))` |
| 4 | `step4_total.py` | country_qty + velocity + 国内库存 + safety_stock_days | `purchase_qty[sku]` | `max(0, Σcountry_qty − (local.available + local.reserved) + ceil(Σvelocity × safety_stock_days))`；`Σvelocity` 覆盖所有国家，不受 `restock_regions` 限制；`buffer_days` 不参与采购量 |
| 5 | `step5_warehouse_split.py` | country_qty + 订单邮编 + 邮编规则 + 国家规则仓映射 | `warehouse_breakdown[country][wh_id]` | 按邮编规则分配到具体仓库；仅“该国家已配置邮编规则”的仓参与分仓与均分兜底；若无规则仓则该国家不分仓；若配置 `restock_regions`，仅消费这些国家的订单明细作为分仓依据；同优先级 tied 均分 |
| 6 | `step6_timing.py` | sale_days + lead_time + country_qty | `urgent` + `restock_dates` | `urgent` 仍按任一正补货国家 `sale_days <= lead_time_days`；`restock_date[sku][country] = today + int(sale_days[sku][country]) − lead_time_days`，仅对正补货国家输出，缺少 sale_days 时记为 `null` |

**运行上下文**：`EngineContext` 包含 `target_days`、`buffer_days`、`lead_time_days`、`safety_stock_days`、`restock_regions`、`eu_countries` 和本次请求的 `demand_date`。`buffer_days` 作为全局配置快照保留，但当前仅用于追溯，不参与 `purchase_qty` 或 `restock_dates` 计算；`global_config.eu_countries` 由同步层消费，`global_config_snapshot` 会冻结这些全局参数与 `demand_date` 以便追溯。

**持久化**：一次完整计算在事务内执行，受 `pg_advisory_xact_lock(7429001)` 保护；runner 先按真实当天口径计算完整中间结果，再按需求截止日期 `demand_date` 仅保留 `restock_dates[country] <= demand_date` 的国家，过期未处理补货国家也会纳入截止范围，`restock_dates[country]` 为空时不纳入补货范围；命中后收缩 `country_breakdown` / `warehouse_breakdown` / `restock_dates` 并重算 `total_qty` / `urgent`；`purchase_qty` 沿用过滤前 SKU 口径。若无补货国家命中但 `purchase_qty > 0`，仍保留为采购-only 条目，并将 `country_breakdown` / `warehouse_breakdown` / `allocation_snapshot` / `restock_dates` 清空、`total_qty=0`、`urgent=false`；若过滤后无条目则返回 `None`，不归档旧 `draft`、不关闭生成开关、不生成空建议单；成功生成非空建议单后才归档旧 `draft`，写入 `suggestion` / `suggestion_item`，统计 `procurement_item_count`、`restock_item_count`，并由 `calc_engine_job` 将 `global_config.suggestion_generation_enabled` 自动翻 OFF。

**快照字段**：`velocity_snapshot`、`sale_days_snapshot`、`allocation_snapshot`、`global_config_snapshot` 均以 JSONB 保存；其中 `velocity_snapshot` / `sale_days_snapshot` 保留过滤前完整 SKU 追溯数据，`global_config_snapshot.demand_date` 记录业务需求截止日期；`suggestion_item.purchase_qty` 用于采购视图，`country_breakdown` / `warehouse_breakdown` 用于补货视图，`restock_dates` 用于截止过滤、追溯与 Excel 导出（前端不展示）。

### 3.2 数据同步层（app/sync）

**职责**：从赛狐 API 增量同步店铺、仓库、商品、订单、库存、出库记录到本地库。

**模式**：每个赛狐资源对应一个 sync job；另外允许少量仅落本地库的修复型任务，用于历史数据回填：

```python
@register("sync_inventory")
async def sync_inventory_job(ctx: JobContext) -> None:
    await mark_sync_running(db, JOB_NAME)
    try:
        async for raw in list_inventory_items(...):  # Saihu 分页拉取
            await _upsert_inventory(db, raw, warehouse_country_map)
            if count % 100 == 0:
                await db.commit()
        await mark_sync_success(db, JOB_NAME, started)
    except Exception as exc:
        await mark_sync_failed(db, JOB_NAME, str(exc))
        raise
```

**批量 UPSERT**：使用 `pg_insert(...).on_conflict_do_update(...)` 模式，避免先 SELECT 后 INSERT/UPDATE 的竞态。

**状态追踪**：每个 job 在 `sync_state` 表中维护最后运行时间、状态、错误信息。

**出库记录同步**：`sync_out_records` 会把赛狐“其他出库”记录同步到 `in_transit_record` / `in_transit_item`，除在途状态观测所需字段外，还保留 `warehouseId`、`updateTime`、`type/typeName`、`commodityId`、`perPurchase`，用于数据页直接展示“出库”主表和明细表字段。`target_country` 改为从备注文本提取国家名（如 `20260410美国-赢捷-加州-散货-在途中` → `US`）；提取失败时保持空值，不再回退到 `targetFbaWarehouseId -> warehouse.country`。每次执行该同步任务后，还会顺带扫描历史 `target_country` 为空的旧记录并按同一备注规则回填，不覆盖已有值。

**订单详情获取**：除自动 `sync_order_detail` 外，订单页还提供右侧独立“详情获取”组件，前端仅提交回溯天数到 `POST /api/sync/order-detail/refetch`。接口层会先检查活跃的 `refetch_order_detail`、`sync_order_detail`、`sync_all` 任务并直接返回现有 task_id，避免手动触发与定时 / 全量同步并发重复抓取；仅在无冲突时才按“最近 N 天”筛选本地缺少详情的全部订单并创建 `refetch_order_detail` TaskRun 后台任务，不再设置手动单次数量上限。该任务绕过 `order_detail_fetch_log` 的去重过滤，但继续复用既有失败分类、2 QPS / 2 并发抓取与落库逻辑，并按“已完成 X / 失败 Y / 总数 N”精确回写进度。

### 3.3 任务队列系统（app/tasks）

**核心表**：`task_run`

```sql
CREATE TABLE task_run (
  id BIGSERIAL PRIMARY KEY,
  job_name VARCHAR NOT NULL,
  status VARCHAR NOT NULL,  -- pending / running / success / failed / skipped / cancelled
  dedupe_key VARCHAR,
  trigger_source VARCHAR,   -- scheduler / manual / api
  priority INT DEFAULT 0,
  payload JSONB,
  worker_id VARCHAR,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  heartbeat_at TIMESTAMPTZ,
  lease_expires_at TIMESTAMPTZ,
  current_step VARCHAR,
  step_detail TEXT,
  total_steps INT,
  error_msg TEXT,
  result_summary TEXT
);

-- 活跃任务去重（仅对 pending/running 生效）
CREATE UNIQUE INDEX uq_task_run_active_dedupe 
  ON task_run (dedupe_key) 
  WHERE status IN ('pending', 'running');

-- Worker 调度索引（仅 pending）
CREATE INDEX ix_task_run_pending_priority 
  ON task_run (status, priority, created_at) 
  WHERE status = 'pending';

-- Reaper 过期索引（仅 running）
CREATE INDEX ix_task_run_lease 
  ON task_run (lease_expires_at) 
  WHERE status = 'running';
```

**四个组件协同**：

```
┌───────────────┐    enqueue    ┌──────────┐    claim     ┌────────┐
│   Scheduler   │──────────────▶│ task_run │◀─────────────│ Worker │
│ (APScheduler) │               │   (DB)   │              │ (poll) │
└───────────────┘               └─────┬────┘              └────────┘
       ▲                              │                        │
       │                              │ reap expired           │ heartbeat
       │ cron/interval                ▼                        │
       │                        ┌──────────┐                   │
       └────── register jobs ───┤  Reaper  │◀──────────────────┘
                                └──────────┘
```

- **Scheduler**：APScheduler 按间隔/cron 触发，调用 `enqueue_task()`（不直接执行任务）
- **Worker**：每 2 秒轮询一次，用 `FOR UPDATE SKIP LOCKED` 原子抢占 pending 任务，启动执行 + 心跳协程
- **Reaper**：每 60 秒扫描 `lease_expires_at < now()` 的 running 任务，标记为 failed（worker 死亡回收）
- **Heartbeat**：每 30 秒延长 `lease_expires_at`，约束 `heartbeat × 2 < lease_minutes × 60`

**进度追踪**：`TaskRun.current_step / step_detail / total_steps / result_summary` 由 worker 在执行中写入，前端 `TaskProgress` 组件轮询 `/api/tasks/{id}`。`calc_engine` 在生成成功或无需求时写结构化 JSON 摘要（`generated`、`suggestion_id`、`demand_date`、可选 `reason`）；`sync_order_detail` / `refetch_order_detail` 直接按目标订单数回写精确进度；店铺、仓库、商品、库存、订单、出库等分页同步任务则复用赛狐分页响应里的 `totalPage` 输出“第 P / N 页”进度，不额外发起预扫描请求。自 2026-04-20 起，worker 的 heartbeat、进度更新和 success/failed 终态回写都带 `status='running' + worker_id` 条件；若租约已被 reaper 回收，则抛 `TaskLeaseLostError` 并停止继续覆盖状态。
**信息总览快照任务**：`refresh_dashboard_snapshot` 也是标准 TaskRun 任务，复用现有去重、轮询和失败回写机制；它在后台调用 `build_dashboard_payload()` 生成 `dashboard_snapshot` 单例缓存，页面刷新时优先消费该缓存而不是重复现算。
**任务权限注册表**：`app/tasks/access.py` 统一维护 TaskRun 作业清单，以及查看/操作权限映射；通用 `POST /api/tasks` 只允许创建显式白名单里的任务。`push_saihu` 作业与推送链路已随 §3.6 的导出快照子系统一同删除。

### 3.4 赛狐集成层（app/saihu）

**单例客户端 + 端点包装器 + Token 管理 + 限流 + 重试**：

```
调用方
  │
  ▼
endpoints/xxx.py  ← 薄包装，负责参数构造和分页迭代
  │
  ▼
SaihuClient.post()  ← 统一重试 + 日志
  │
  ├─▶ TokenManager.get_token()  ← 单飞模式 + 5 分钟预刷新
  │
  ├─▶ rate_limit.get_limiter(endpoint)  ← per-endpoint QPS
  │
  ├─▶ httpx.AsyncClient.post()  ← 实际 HTTP
  │
  └─▶ ApiCallLog INSERT  ← 每次调用必记录
```

**重试策略**（tenacity）：
- 指数退避：1s → 2s → 4s → 10s
- 可重试：`SaihuRateLimited`（40019）、`SaihuNetworkError`
- 不重试：`SaihuBizError`（业务错误码）
- **特殊处理**：`SaihuAuthExpired`（40001）→ 在重试预算**之外**强制刷新 token 后再重试一次

**限流**：
```python
_ENDPOINT_RATE_OVERRIDES = {
    "/api/order/detailByOrderId.json": 3,  # 该接口放宽到 3 QPS
}
# 默认 1 QPS per endpoint
```

**Token 单飞**：并发 `get_token()` 调用共享同一个刷新 Future，避免同时发起多个刷新请求。

### 3.5 横切关注点

| 关注点 | 实现 | 位置 |
|---|---|---|
| **认证** | JWT HS256，24h 有效，单用户 `sub="owner"` | `core/security.py`, `api/deps.py` |
| **异常** | `BusinessError` 层次（NotFound/Unauthorized/ValidationFailed/...）+ `SaihuAPIError` 层次，全局 exception handler 转 JSON | `core/exceptions.py`, `main.py:113-131` |
| **日志** | structlog + contextvars 绑定 `request_id`，dev ConsoleRenderer / prod JSONRenderer | `core/logging.py`, `core/middleware.py` |
| **中间件** | `RequestLoggingMiddleware` 记录 method/path/status/duration_ms，注入 X-Request-Id 响应头 | `core/middleware.py` |
| **应用限流** | 进程内 IP 滑动窗口限流，定期清理过期客户端并在超过容量上限时驱逐最旧 key | `core/rate_limit.py` |
| **时区** | 存储 UTC，展示北京时间；`parse_saihu_time` 按 marketplace_id 推断源时区再转换 | `core/timezone.py` |
| **配置** | `pydantic-settings` 从环境变量/`.env` 加载，`get_settings()` 单例 | `config.py` |

### 3.6 导出快照子系统（app/services + app/api/snapshot.py）

**定位**：取代原“推送采购单到赛狐”链路，改为“建议单 → 用户勾选采购/补货条目 → 生成不可变 Snapshot + Excel 文件 → 用户下载”的工作流。采购与补货从 API、快照版本、条目导出状态和 Excel 格式上完全拆分。

**核心表**：

| 表 | 职责 | 关键字段 |
|---|---|---|
| `suggestion_snapshot` | 一次导出即一个 snapshot；冻结 `snapshot_type`、`version`、`exported_by`、`exported_from_ip`、`global_config_snapshot`、`item_count`、`generation_status`、`file_path`、`file_size_bytes`、`download_count` | FK `suggestion_id`，`UNIQUE(suggestion_id, snapshot_type, version)` |
| `suggestion_snapshot_item` | snapshot 冻结的条目副本；采购快照保存 `purchase_qty`，补货快照保存 `total_qty` / `country_breakdown` / `warehouse_breakdown` / `restock_dates` | FK `snapshot_id` ON DELETE CASCADE |
| `suggestion_item` | 当前 draft 可编辑条目；采购导出状态与补货导出状态独立 | `purchase_qty` 供采购视图；`country_breakdown` / `warehouse_breakdown` 供补货视图；`restock_dates` 供截止过滤、追溯与 Excel 导出；`procurement_export_status` / `procurement_exported_snapshot_id` / `procurement_exported_at`，`restock_*` 同构 |

**API 端点**：

| 端点 | 行为 |
|---|---|
| `POST /api/suggestions/{id}/snapshots/procurement` | 创建采购快照；选中条目必须存在 `purchase_qty > 0` |
| `POST /api/suggestions/{id}/snapshots/restock` | 创建补货快照；选中条目必须存在 `sum(country_breakdown) > 0` |
| `POST /api/suggestions/{id}/snapshots` | 旧端点保留为 410 Gone，避免调用方误用旧混合导出 |
| `GET /api/suggestions/{id}/snapshots?type=procurement|restock` | 按类型过滤快照列表；不传 type 返回两类 |
| `GET /api/snapshots/{snapshot_id}` | 读取快照详情与冻结条目 |
| `GET /api/snapshots/{snapshot_id}/download` | 下载 Excel，同时增加下载计数 |

**导出流程**：

1. `SELECT ... FOR UPDATE` 锁定建议单、导出条目和 `global_config(id=1)`。
2. 校验建议单仍为 `draft`，校验条目属于该建议单，按 `snapshot_type` 校验采购量或补货量。
3. 按 `(suggestion_id, snapshot_type)` 独立计算下一版 `version`。
4. INSERT `suggestion_snapshot(generation_status='generating')` 与 `suggestion_snapshot_item`。
5. `excel_export.py` 根据类型生成不同工作簿：采购为“主数据 + 采购明细”，补货为“主数据 + SKU汇总 + SKU×国家 + SKU×国家×仓库”；“主数据”记录 `global_config_snapshot.demand_date` 对应的“需求截止日期”，采购/补货明细表不增加需求截止日期列；补货工作簿在国家与仓库明细中导出 `restock_dates` 对应的“补货日期”，前端当前补货视图与历史详情弹窗不展示补货日期。
6. 文件成功落盘后，才更新对应条目的 `{type}_export_status='exported'`、`{type}_exported_snapshot_id`、`{type}_exported_at`。
7. 更新 `suggestion_snapshot.generation_status='ready'`、`file_path`、`file_size_bytes`。

**失败补偿**：若 Excel 生成或文件落盘失败，则 snapshot 记为 `failed`，不修改任何条目的采购/补货导出状态，用户可直接重试同类型导出。

## 4. 前端核心组件

### 4.1 目录结构

```
src/
├── views/           # 页面（18 个）
│   ├── LoginView / WorkspaceView / NotFoundView
│   ├── SuggestionListView / SuggestionDetailView / HistoryView
│   ├── data/        # 6 个数据页
│   └── SyncConsoleView / GlobalConfigView / ZipcodeRuleView / ApiMonitorView / PerformanceMonitorView
├── components/      # 可复用组件
│   ├── AppLayout / PageSectionCard / SkuCard / StatusTag / TablePaginationBar / TaskProgress
│   ├── charts/      # BaseChart (ECharts wrapper)
│   ├── dashboard/   # Dashboard 专用卡片
│   └── sync/        # 同步专用组件
├── api/             # API 客户端（每个领域一个文件）
├── stores/          # Pinia 状态（auth / sidebar / task）
├── router/          # 路由 + 鉴权守卫
├── utils/           # 工具函数（format / tableSort / countries / warehouse / status / monitoring / storage / download / ...）
├── styles/          # 设计系统（tokens.scss + element-overrides.scss）
├── config/          # 页面元数据与导航配置
└── main.ts
```

`components/dashboard/` 中的 `DashboardChartCard` 当前除标准图表卡片外，还支持在图表下方渲染自定义 footer 区域，用于信息总览页这类“上图下图例”布局；图表撑满高度的样式仅在存在 footer 时启用，普通图表卡片保持原有自适应高度。

**导出链路前端文件关系**：`frontend/src/api/snapshot.ts` 对接后端 `app/api/snapshot.py`（创建 / 列表 / 详情 / 下载）；新增共享工具 `frontend/src/utils/download.ts`（`triggerBlobDownload`）被 `SuggestionDetailView` 的"导出 Excel"按钮与"历史快照区"下载流程共同引用。`api/snapshot.ts` 在 `downloadSnapshotBlob` 中解析 `Content-Disposition` 文件名并回传给 `triggerBlobDownload`，保持 blob 下载行为在全前端只有一份实现。

### 4.2 设计系统

**基于 shadcn/ui Zinc 主题**，在 `src/styles/tokens.scss` 中定义：
- **颜色**：50+ 设计令牌，主色 `#18181b`（zinc-900）
- **间距**：4px 网格（`$space-1` 至 `$space-16`）
- **字体**：Inter + JetBrains Mono
- **圆角**：4 / 6 / 8 / 12 / pill
- **阴影**：card / popup 两级

`element-overrides.scss` 通过 Element Plus 的 `--el-*` CSS 变量机制，将所有 UI 组件样式对齐到设计令牌。

### 4.3 状态管理

| Store | 状态 | 持久化 |
|---|---|---|
| `useAuthStore` | token, user, isAuthenticated | localStorage（异常 JSON 会自动清理） |
| `useSidebarStore` | isCollapsed, expandedCategories | localStorage（异常 JSON 会自动清理） |
| `useTaskStore` | tasksById, polling | 内存（刷新丢失） |

**全局状态仅保留 3 个 store**，其余状态局部保存在 view 的 `ref/reactive` 中。

### 4.4 API 客户端

`frontend/src/api/*` 按后端资源拆分：

| 文件 | 职责 |
|---|---|
| `suggestion.ts` | 建议单列表、当前建议、详情、条目 PATCH、删除；`Suggestion` 携带 `procurement_item_count` / `restock_item_count` / `procurement_snapshot_count` / `restock_snapshot_count`，`SuggestionItem` 携带 `purchase_qty` 与两组导出状态 |
| `snapshot.ts` | `createProcurementSnapshot()`、`createRestockSnapshot()`、`listSnapshots(id, type?)`、详情与下载；`SnapshotOut.snapshot_type` 为 `procurement` / `restock` |
| `config.ts` | `GlobalConfig` 暴露 `safety_stock_days`、`eu_countries`、`restock_regions` 等现行字段；`GenerationToggle` 暴露 `can_enable` / `can_enable_reason` |
| `engine.ts` / `task.ts` | 手动触发必填 `demand_date` 的 `POST /api/engine/run`；`task.ts` 同时封装 `getTask()` 与 `listTasks()`，当前建议页会分别查询 `calc_engine` 的 `pending` / `running` 任务以复用进度 |

所有 API 客户端继续通过 `api/client.ts` 注入 Bearer token，并复用统一错误处理与 401 跳转逻辑。

### 4.5 数据流模式

**高增长数据页默认模式：“后端分页 + 后端筛选”**：

```typescript
const rows = ref<T[]>([])                    // 当前页数据
const total = ref(0)
const filters = reactive({ ... })            // 筛选条件
const page = ref(1)
const pageSize = ref(50)

async function reload() {
  const resp = await listData({
    page: page.value,
    page_size: pageSize.value,
    ...filters,
  })
  rows.value = resp.items
  total.value = resp.total
}
```

当前已按该模式迁移：
- `DataOrdersView.vue`：订单列表按页返回，并仅对当前页补查 `item_count` / `has_detail`
- `HistoryView.vue`：建议单历史页直接消费 `GET /api/suggestions` 的 `items/total/page/page_size`；状态列使用 `getSuggestionDisplayStatusMeta(status, snapshot_count)` 派生 4 档显示标签（`未提交 / 已导出 / 已归档 / 异常`），状态下拉对应后端 `display_status=pending|exported|archived|error`，由后端统一按 `snapshot_count` 派生过滤，避免前端只过滤当前页造成 `items` 与 `total` 错位；`canDelete(row)` 规则为 `row.snapshot_count === 0`。派生逻辑定义在 `frontend/src/utils/status.ts::deriveSuggestionDisplayStatus`，`SuggestionListView` 与 `SuggestionDetailView` 的状态 tag 共用该函数，避免多处硬编码映射。
- `DataProductsView.vue`：商品页通过 `listSkuOverview()` 下推 SKU、启用状态和分页参数
- `DataInventoryView.vue`：库存页通过 `GET /api/data/inventory/warehouse-groups` 做仓库分组分页，保持仓库展开明细交互
- `DataOutRecordsView.vue`：出库记录页将 SKU、仓库单号、国家、类型、在途状态、排序和分页下推到后端

**订单页排序示例**：

```typescript
const rows = ref<T[]>([])                    // 当前页数据
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

async function reload() {
  const resp = await listOrders({
    page: page.value,
    page_size: pageSize.value,
    shop_id: filters.shop || undefined,
    sort_by: sortState.value.prop,
    sort_order: sortState.value.order,
  })
  rows.value = resp.items
  total.value = resp.total
}
```

订单页最早切换到服务端分页，是因为订单量增长最快，且 `item_count` / `has_detail` 需要额外聚合查询；继续“一次拉全量”会同时放大后端查询和前端渲染成本。后续迁移把同一原则扩展到历史记录、商品、库存和出库记录页。

**轻量基础页例外**：店铺、仓库等低增长基础数据页仍可保留简单分页；新建可能超过数千条的列表页时，优先采用服务端分页模式。

### 4.6 路由与鉴权

路由统一定义在 `frontend/src/router/index.ts`，并通过 `RouteMeta.permission` 做前端访问控制。核心补货路由已改为嵌套 Tab：

| 父路由 | 默认重定向 | 子路由 |
|---|---|---|
| `/restock/current` | `/restock/current/procurement` | `procurement` 当前采购建议，`restock` 当前补货建议 |
| `/restock/suggestions/:id` | `/restock/suggestions/:id/procurement` | `procurement` 建议单采购详情，`restock` 建议单补货详情 |
| `/restock/history` | `/restock/history/procurement` | `procurement` 采购快照历史，`restock` 补货快照历史 |

`SuggestionTabBar` 根据当前路径切换子路由；父容器负责加载建议单、生成开关、任务进度和公共 header，子视图只负责采购/补货数据展示与导出动作。`authGuard` 在 `beforeEach` 中检查登录态与权限，失败时跳转 `/login?redirect=<origin>` 或 `/403`。

### 4.7 共享组件模式

| 组件 | 用途 | 复用位置 |
|---|---|---|
| `PageSectionCard` | 统一页面卡片容器，`title` + `#actions` slot | 所有列表页 |
| `SkuCard` | 商品展示（图片 + 名称 + SKU + blocker 标签） | 商品、库存、订单、建议单 |
| `StatusTag` | 状态标签（基于 StatusMeta 对象） | 所有状态展示 |
| `TablePaginationBar` | 分页条，v-model 绑定 currentPage 和 pageSize | 所有数据表格 |
| `TaskProgress` | 长任务进度展示，自动轮询 `/api/tasks/{id}`；可解析按条数和按页数/步骤的确定型进度；任务读取权限按 `job_name` 映射到对应业务权限过滤 | 引擎生成、同步 |
| `sync/OrderDetailFetchAction` | 订单页右侧“详情获取”动作组件，封装回溯天数、触发逻辑与冲突提示 | 订单页 |

**前端监控命名约定**：
- `src/utils/monitoring.ts` 统一负责监控页的名称展示口径，包括赛狐接口 `endpoint`、性能监控 `request/resource` 名称中文化，以及 tooltip 中保留原始路径
- `ApiMonitorView`、`PerformanceMonitorView`、`sync/FailedApiCallTable` 只消费该工具，不在页面内各自维护映射表，避免图表、表格、tooltip 口径漂移

**信息总览页口径**：
- `WorkspaceView` 首行卡片展示补货概览：`restock_sku_count` 为按当前补货引擎口径计算后 `total_qty > 0` 的启用 SKU 数，`no_restock_sku_count` 为其余启用 SKU 数，`risk_country_count` 表示当前快照中进入风险分层的国家数
- 左图使用分组柱状图展示各国缺货风险分布，统计对象是实时计算后写入 `dashboard_snapshot.payload.country_risk_distribution` 的 SKU+国家数量，而不是当前建议单快照
- “急需补货SKU”列表同样使用快照中的国家级 `sale_days`，一行只表示一个 SKU 在一个国家上的风险，不再按 SKU 聚合
- 右图继续使用饼图，数据仍为 `country_restock_distribution`，即当前建议单全部条目的 `country_breakdown` 汇总，用于展示实际建议补货量的国家分布

**建议单与全局配置视图职责**：

| 视图 | 职责 |
|---|---|
| `SuggestionListView` | 顶部 `PageSectionCard.actions` 展示生成开关只读状态 tag 与当前建议 `需求截止日期`；发起区使用默认空的需求截止日期选择器，提交前校验空值与早于北京时间今天；`loadToggle()` + `loadActiveEngineTask()` 在 `onMounted` / `onActivated` 双钩子刷新开关与活跃 `calc_engine` 任务，活跃任务存在时复用 `TaskProgress` 并禁用日期选择器与生成按钮。已移除推送时代的选择列、推送按钮、`pushTaskId` 轮询、`selectedIds` / `handleSelection` / `handleSelectAll` / `syncTableSelection` / `handlePush` / `PUSH_STATUS_SORT_ORDER` / `filterPushStatus` 等死代码。 |
| `SuggestionDetailView` | 勾选 `export_status='pending'` 的条目 → “导出 Excel”按钮走一步式 `POST /api/suggestions/{id}/snapshots` + `GET /api/snapshots/{id}/download` blob 流程（失败时仍在 `finally` 中 `await load()` 刷新快照历史，并区分”导出成功但下载失败”的独立错误文案）；右侧新增”历史快照区”`PageSectionCard`（6 列，按 `version` 降序，可重复下载）；导出前会先探测生成开关，探测失败时按 fail-close 禁用按钮；`SkuCard` 停止传入 `:blocker`（组件 prop 仍保留但所有调用点不再传值）；条目 `isEditable` 改为 `export_status !== 'exported'`（对应 snapshot 条目不可变的约束，见 §9.5 Don'ts）。 |
| `GlobalConfigView` | 新增”生成开关卡片”：`el-switch` 即时保存，翻 ON 时弹 `ElMessageBox` 二次确认”将归档全部 draft”，`PATCH` 失败时回滚开关状态并提示；无 `config:edit` 时控件只读并提示”无权限操作此开关”。 |
| `HistoryView` | 参见 §4.5 — 状态筛选 3 项，快照数 + 导出状态列，`canDelete` 基于 `snapshot_count === 0`。 |

---

## 5. 数据流程示例

### 场景 1：用户触发采补计算

```text
用户选择需求截止日期并点击“生成采补建议”
  ↓
POST /api/engine/run { demand_date: "YYYY-MM-DD" }
  ↓
api/sync.py: 校验需求截止日期不早于北京时间今天，enqueue_task("calc_engine", "manual")
  ↓
task_run 表 INSERT status=pending, dedupe_key="calc_engine"
  ↓
worker 抢占任务 → calc_engine_job
  ↓
run_engine 读取 global_config：target_days / buffer_days / lead_time_days / safety_stock_days / restock_regions / eu_countries，并读取 payload.demand_date
  ↓
pg_advisory_xact_lock(7429001)
  ↓
6 步流水线：velocity → sale_days → country_qty → purchase_qty → warehouse_split → urgent/restock_dates
  ↓
按 demand_date 过滤截止日前到期国家（`restock_dates[country] <= demand_date`）；无命中则返回 no_suggestion_needed
  ↓
有命中时 INSERT suggestion + suggestion_item[]，写入采购/补货 item_count 和配置快照（含 demand_date）
  ↓
成功生成非空建议单后 suggestion_generation_enabled=false
  ↓
前端 TaskProgress 轮询成功 → 刷新采购/补货 Tab
```

### 场景 2：采购 / 补货快照独立导出

```text
用户在采购或补货 Tab 勾选条目
  ↓
采购：POST /api/suggestions/{id}/snapshots/procurement
补货：POST /api/suggestions/{id}/snapshots/restock
  ↓
锁定 suggestion + item + global_config
  ↓
按 snapshot_type 校验条目与独立递增 version
  ↓
INSERT suggestion_snapshot(snapshot_type, generation_status='generating')
  ↓
INSERT suggestion_snapshot_item[]，冻结采购字段或补货拆分字段
  ↓
生成采购/补货专属 Excel 工作簿并落盘
  ↓
UPDATE suggestion_item SET procurement_* 或 restock_* 导出状态
  ↓
GET /api/snapshots/{snapshot_id}/download 下载文件
```

### 场景 3：开新周期（翻生成开关并归档 draft）

```text
用户在全局参数页点击开启生成开关
  ↓
GET /api/config/generation-toggle 返回 can_enable / can_enable_reason
  ↓
PATCH /api/config/generation-toggle { enabled: true }
  ↓
后端事务内再次校验：若采购/补货 item_count>0，则对应类型必须已有至少 1 个 snapshot
  ↓
UPDATE suggestion SET status='archived', archived_trigger='admin_toggle', archived_by=<user>, archived_at=now
  ↓
UPDATE global_config SET suggestion_generation_enabled=true, generation_toggle_updated_by/at=...
  ↓
下一次手动 calc_engine 生成新 draft，并在成功后再次自动翻 OFF
```

## 6. 数据库设计

### 6.1 核心表

| 表 | 职责 | 关键约束 / 字段 |
|---|---|---|
| `global_config` | 全局配置单行表；包含 `target_days`、`buffer_days`、`lead_time_days`、`safety_stock_days`、`restock_regions`、`eu_countries`、`suggestion_generation_enabled`、`generation_toggle_updated_by / generation_toggle_updated_at`、同步与登录配置 | `CHECK id=1`；`safety_stock_days` 范围 1–90；`restock_regions=[]` 表示全部国家参与补货计算 |
| `sku_config` | SKU 启用 / 禁用与业务参数 | `commodity_sku` 唯一 |
| `warehouse` | 海外仓/国内仓基础资料 | `country` 可为空；变更仓库国家会级联更新库存最新快照口径 |
| `order_header` / `order_item` | 订单头与订单明细 | `order_header.country_code` 保存映射后国家，`original_country_code` 保存 EU 合并前国家；按 `shop_id + purchase_date`、`order_status + purchase_date` 建索引 |
| `product_listing` | 赛狐在线产品信息 | `marketplace_id` 保存映射后 2 字符国家码或 `EU`，`original_marketplace_id` 保存 EU 合并前国家 |
| `inventory_snapshot_latest` | SKU × 仓库最新库存 | `country` 保存映射后国家，`original_country` 保存 EU 合并前国家；`warehouse_id + commodity_sku` 唯一 |
| `in_transit_record` / `in_transit_item` | 出库 / 在途记录与明细 | `target_country` 保存映射后国家，`original_target_country` 保存 EU 合并前国家 |
| `suggestion` | 建议单头 | `status IN ('draft','archived','error')`；`procurement_item_count` / `restock_item_count` 分别统计采购与补货需求 SKU 数 |
| `suggestion_item` | 当前建议条目 | `purchase_qty` 供采购视图；`country_breakdown` / `warehouse_breakdown` 供补货视图；`restock_dates` 供截止过滤、追溯与 Excel 导出；采购与补货各自拥有 `*_export_status`、`*_exported_snapshot_id`、`*_exported_at` |
| `suggestion_snapshot` | 导出快照头（§3.6） | `snapshot_type IN ('procurement','restock')`；`UNIQUE(suggestion_id, snapshot_type, version)`；`generation_status IN ('generating','ready','failed')` |
| `suggestion_snapshot_item` | 导出快照条目副本 | FK `snapshot_id` ON DELETE CASCADE；冻结 `purchase_qty`、`restock_dates` 与补货拆分 JSONB |
| `excel_export_log` | Excel 下载审计 | 记录 snapshot、操作者、IP、User-Agent、文件大小等 |
| `task_run` | 后台任务队列 | `dedupe_key + active status` partial unique index |
| `dashboard_snapshot` | 信息总览缓存快照 | 单例缓存 dashboard payload、刷新状态与错误信息 |
| `api_call_log` | 赛狐 API 调用日志 | 按时间范围查询 |
| `login_attempt` | 登录尝试与锁定状态 | `source_key` PK |

#### `zipcode_rule`（邮编→仓库规则）

- 字段：`country`, `prefix_length`, `value_type`, `operator`, `compare_value`, `warehouse_id`, `priority`
- `operator ∈ {=, !=, >, >=, <, <=, contains, not_contains, between}`（`String(10)`，CHECK 约束 `operator_enum`）
- `compare_value: String(200)`，`between` 运算符承载一段或多段 `lo-hi` 闭区间（多段逗号分隔，最多 20 段，`hi ≤ 10^prefix_length - 1`）
- 按 `(country, priority)` 升序匹配，首条命中返回仓库；全部未命中归"未知仓"
- **tied 配置**：把多条规则的 `priority` 填相同值即触发同优先级均分；tied 定义基于命中该具体订单的最低 priority 批次，跨 operator 通用

### 6.2 关键索引策略

**部分索引**（Partial Index）：
- `uq_task_run_active_dedupe`：仅对活跃任务去重，历史任务不占索引空间
- `ix_task_run_pending_priority`：Worker 调度查询加速
- `ix_task_run_lease`：Reaper 扫描过期任务加速
- `ix_suggestion_item_urgent`：仅索引紧急条目

**JSONB 字段**：`country_breakdown`、`warehouse_breakdown`、`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot`、`allocation_snapshot`、`payload`。其中 `global_config_snapshot` 会保留 `restock_regions` 等配置快照。当前仅整体读取，不查 JSONB 内部字段，无需 GIN 索引。

### 6.3 迁移管理

- 工具：Alembic（命名规范配置在 `db/base.py` 的 NAMING_CONVENTION）
- 位置：`backend/alembic/versions/`
- 命名：`YYYYMMDD_HHMM_description.py`
- 执行：`alembic upgrade head`（容器启动时由 deploy 脚本自动执行）

---

## 7. 部署架构

### 7.1 Docker Compose 拓扑

```
┌──────────┐
│  Caddy   │ :443  ← HTTPS terminator，Let's Encrypt 自动证书
└────┬─────┘
     │
     ├─────▶ /api/*, /docs, /healthz, /readyz ─▶ ┌──────────┐
     │                                            │ backend  │ :8000
     └─────▶ 其他静态资源 ─▶ ┌────────────┐      │ FastAPI  │
                             │  frontend  │      └─────┬────┘
                             │   nginx    │            │
                             └────────────┘            │
                                                       ▼
                                                 ┌──────────┐
                                                 │    db    │ :5432
                                                 │ Postgres │
                                                 └──────────┘
                                                       ▲
                                                       │
                                            ┌──────────┴──────────┐
                                            │                     │
                                       ┌────┴────┐          ┌─────┴──────┐
                                       │ worker  │          │ scheduler  │
                                       │ 同 FastAPI 镜像   │  同 FastAPI  │
                                       └─────────┘          └────────────┘
```

**资源限制**：
- db: 1GB
- backend: 512MB
- worker: 512MB
- scheduler: 512MB
- frontend (nginx): 256MB
- caddy: 128MB

### 7.2 进程分离策略

后端镜像同一份，通过环境变量决定启用哪些组件：

```env
# backend 实例：只服务 HTTP
PROCESS_ENABLE_WORKER=false
PROCESS_ENABLE_REAPER=false
PROCESS_ENABLE_SCHEDULER=false

# worker 实例：只跑任务
PROCESS_ENABLE_WORKER=true
PROCESS_ENABLE_REAPER=true
PROCESS_ENABLE_SCHEDULER=false

# scheduler 实例：只调度
PROCESS_ENABLE_WORKER=false
PROCESS_ENABLE_REAPER=false
PROCESS_ENABLE_SCHEDULER=true
```

这样可以水平扩展 Worker，Scheduler 保持单例避免重复触发。

### 7.3 部署脚本（deploy/scripts/）

| 脚本 | 用途 |
|---|---|
| `deploy.sh` | 完整部署：验证 env → 备份 → 迁移 → 拉新镜像 → 滚动更新 → smoke check → 失败自动回滚 |
| `migrate.sh` | 仅执行数据库迁移 |
| `pg_backup.sh` | PostgreSQL 备份 |
| `restore_db.sh` | 从备份恢复 |
| `rollback.sh` | 回滚到上一个成功版本 |
| `validate_env.sh` | 验证环境变量完整性 |
| `smoke_check.sh` | 部署后健康检查（/healthz, /readyz） |

`deploy.sh` 在未显式传入 `IMAGE_TAG` 时，会默认使用当前仓库 HEAD 派生 `sha-<commit>`，与 CI 发布到 GHCR 的镜像标签保持一致；GitHub Actions 部署也是同一口径。

### 7.4 健康检查

- **`GET /healthz`**：存活探针，仅返回 `{"status":"ok"}`
- **`GET /readyz`**：就绪探针，检查：
  1. 数据库连通性（`SELECT 1`）
  2. Worker 运行中（或已禁用）
  3. Reaper 运行中（或已禁用）
  4. Scheduler 运行中（或已禁用）

---

## 8. 关键架构决策（ADR 摘要）

### ADR-1：全栈 async

- **决策**：FastAPI + SQLAlchemy async + httpx + asyncio
- **驱动**：系统是 I/O 密集（数据库查询 + 赛狐 HTTP 调用 + 批量文件 I/O），无 CPU bound 任务
- **代价**：开发者需理解 async/await，不能混用同步 I/O

### ADR-2：自研 TaskRun 替代 Celery

- **决策**：`task_run` 表 + 自定义 worker/scheduler/reaper
- **驱动**：
  - 无需 Redis/RabbitMQ broker，减少依赖
  - TaskRun 直接作为领域对象（可查询状态、进度、dedupe、优先级）
  - 进度追踪与任务执行同库同事务，前端轮询简单
- **代价**：放弃 Celery 生态（Flower 监控、重试策略库等）
- **适用范围**：单机或少量机器，超大规模（每秒百 task 以上）才需要真正的分布式队列

### ADR-3：数据库咨询锁而非应用层锁

- **决策**：`pg_advisory_xact_lock` 保证引擎单次运行
- **驱动**：
  - 事务级锁自动释放，无泄漏风险
  - 跨进程生效（同一数据库连接池即可）
  - 非阻塞性（其他查询不受影响）
- **代价**：仅限同一 PostgreSQL 实例

### ADR-4：高增长列表服务端分页

- **决策**：订单、历史、商品、库存、出库记录等高增长列表统一使用 server-side 分页、筛选、排序；店铺、仓库等低增长基础页可保留轻量分页
- **驱动**：
  - 避免前端首屏一次拉取 5000 条导致渲染和交互变慢
  - 避免后端为非当前页数据做额外聚合查询，例如订单 `item_count` / `has_detail`
  - 筛选条件直接下推数据库，数据继续增长时接口耗时更可控
- **代价**：
  - 前后端都要维护分页、筛选、排序状态
  - 跨页选择需要显式维护已选 ID，而不能依赖当前本地数组
- **未来演进**：若单页渲染仍受影响，可在服务端分页基础上叠加虚拟滚动

### ADR-5：PageSectionCard 作为所有页面的统一容器

- **决策**：所有列表页强制使用 `PageSectionCard`（`#title` + `#actions` slot）
- **驱动**：视觉一致性、减少重复 header 代码
- **例外**：
  - `SuggestionDetailView`（详情页 header 复杂，保留原始 `el-card`）
  - `GlobalConfigView` 已迁移

### ADR-6：去重基于已推送建议而非赛狐在途

- **Status**: Superseded by Plan A 2026-04-19（见 §3.6 / PROGRESS.md §3.49）。推送链路已整体删除，本 ADR 的原始决策不再有效，仅保留做审计追溯。
- **Replacement decision**：`load_in_transit` 改回直接读取赛狐同步下来的在途出库记录（`in_transit_record` + `in_transit_item`，按 `is_in_transit=true` 过滤），不再做跨批次"已推送未归档"去重。业务人员通过 Excel 导出 + 线下落单的工作流替代了即时去重诉求；如果需要防止重复下单，现在依靠"首次导出后翻 OFF 生成开关 → 新周期由业务人员显式翻 ON 并归档旧 draft"这一闸门，而不是引擎层的数量冲销。
- **原始决策（已失效）**：`load_in_transit` 从 `suggestion_item` 汇总已推送条目，而非查赛狐在途
- **原始驱动（已失效）**：
  - 赛狐在途数据有同步延迟（需要下次 sync 才写入本地）
  - 已推送建议单立即可查，0 延迟去重
- **原始约束（已失效）**：只考虑近 90 天的已推送建议（避免累积过多历史数据）

---

## 9. 扩展和演进指南

### 9.1 新增一个数据页面

1. **后端**：在 `app/api/data.py` 添加端点（模式参考现有的 `list_orders`）
2. **前端 API**：在 `src/api/data.ts` 添加 TypeScript 接口 + 调用函数
3. **前端页面**：
   - 在 `src/views/data/` 新建 `DataXxxView.vue`
   - 使用 `PageSectionCard` + `#actions` slot 放筛选
   - 用"加载全量 + filteredRows + pagedRows" 模式
   - 用 `formatShortTime`、`formatUpdateTime`、`warehouseTypeLabel` 等共享工具；其中数据页列表里的“同步时间”以及出库页里的“更新时间/同步时间”统一使用 `formatUpdateTime` 输出 `YYYY-MM-DD HH:mm`
4. **路由**：在 `src/router/index.ts` 添加路由
5. **导航**：在 `src/config/navigation.ts` 添加菜单项

### 9.2 新增一个后台任务

1. 在 `app/tasks/jobs/` 或 `app/sync/` 新建 `xxx_job.py`
2. 用 `@register(JOB_NAME)` 装饰器注册
3. 函数签名：`async def xxx_job(ctx: JobContext) -> None`
4. 在开始/结束调用 `mark_sync_running/success/failed`（如果是 sync 类）
5. 在 `app/tasks/scheduler.py` 的 `_register_jobs` 中添加触发规则
6. 手动触发：调用 `enqueue_task(db, job_name=JOB_NAME, trigger_source="manual")`

### 9.3 新增一个引擎 Step

**不推荐**。当前 6 步流水线已经覆盖所有计算需求，新增 step 会破坏既有快照字段的语义。更推荐的做法：
- **修改现有 step**：在已有 step 内增加逻辑
- **新增独立 job**：例如"补货提醒推送"作为独立 task，读取 `suggestion_item` 后发送通知

### 9.4 新增一个赛狐 API 端点

1. 在 `app/saihu/endpoints/` 新建 `xxx.py`
2. 模式参考 `inventory.py`：
   ```python
   async def list_xxx(page_size: int = 100, ...) -> AsyncIterator[dict]:
       client = get_saihu_client()
       page_no = 1
       while True:
           result = await client.post(ENDPOINT, body)
           for row in result["data"]["rows"]:
               yield row
           if 达到末页: return
           page_no += 1
   ```
3. 如需特殊 QPS，在 `rate_limit.py` 的 `_ENDPOINT_RATE_OVERRIDES` 添加
4. 消费方：sync job 调用此 iterator + 批量 UPSERT

### 9.5 架构约束（Don'ts）

- **不要**在 API 层直接写 SQL，走 ORM 或业务函数
- **不要**在引擎 step 中调用外部 API，step 应是纯 DB/计算
- **不要**在 sync job 中做业务计算，sync 只做"抓取 → 落库"
- **不要**绕过 TaskRun 直接在请求线程中跑长任务
- **不要**在 `suggestion_item.procurement_export_status='exported'` 后修改已导出的采购字段，或在 `restock_export_status='exported'` 后修改已导出的补货拆分字段（对应 snapshot 是不可变的历史记录）
- **不要**跳过 `global_config.suggestion_generation_enabled` 开关直接触发 `run_engine`；手动 calc 已接入该短路，且成功生成后会自动翻 OFF
- **不要**在前端 store 中保存业务数据（仅 auth/sidebar/task），业务数据局部在 view 中

---

## 10. 测试策略

### 10.1 后端

| 层级 | 框架 | 覆盖范围 |
|---|---|---|
| 单元测试 | pytest + pytest-asyncio | 引擎各 step、zipcode_matcher、时区转换、签名生成等纯函数 |
| 集成测试 | pytest + TEST_DATABASE_URL | 健康检查端点（需真实数据库，默认 skip） |

**运行**：`cd backend && pytest`

**关键测试文件**：
- `tests/unit/test_engine_step1.py` ~ `test_engine_step6.py`
- `tests/unit/test_zipcode_matcher.py`
- `tests/unit/test_sign.py`（赛狐签名生成）

### 10.2 前端

| 层级 | 框架 | 覆盖范围 |
|---|---|---|
| 单元测试 | Vitest 4 | API 客户端、工具函数、路由守卫、Pinia store |

**运行**：`cd frontend && npm run test`

---

## 11. 开发工作流

### 11.1 本地启动

```bash
# 1. 数据库
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db

# 2. 后端
cd backend
python -m venv .venv
source .venv/bin/activate  # 或 .venv/Scripts/activate (Windows)
pip install -e ".[dev]"
cp .env.example .env  # 编辑 SAIHU_CLIENT_ID 等
alembic upgrade head
uvicorn app.main:app --reload

# 3. 前端
cd frontend
npm install
npm run dev
```

### 11.2 质量检查

```bash
# 后端
cd backend
ruff check .
black --check .
mypy app
pytest

# 前端
cd frontend
npm run lint
npm run type-check
npm run test
npm run build
```

### 11.3 提交规范

- 小而频繁的提交
- 提交信息使用 conventional commits：`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`
- PR 前运行完整的 lint + test + build

---

## 12. 架构治理

### 12.1 一致性维护

- **CLAUDE.md**（项目根）：记录技术栈和最近变更，AI 助手和新成员优先阅读
- **docs/superpowers/specs/**：保留每个重要设计的 spec 文档
- **docs/superpowers/plans/**：保留每次实施计划
- **本文档**：架构层级的真理源（Source of Truth）

### 12.2 架构变更流程

1. 先用 `superpowers:brainstorming` skill 讨论设计
2. 写 spec 到 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
3. 用户审阅通过
4. 用 `superpowers:writing-plans` 生成可执行计划
5. 用 `superpowers:subagent-driven-development` 执行
6. 每步通过校验后才算验收
7. 更新本架构蓝图（如涉及架构变更）

---

## 附录 A：关键文件速查

| 功能 | 文件 |
|---|---|
| 引擎编排 | `backend/app/engine/runner.py` |
| 任务队列 | `backend/app/tasks/queue.py` |
| Worker 循环 | `backend/app/tasks/worker.py` |
| 调度器 | `backend/app/tasks/scheduler.py` |
| 赛狐客户端 | `backend/app/saihu/client.py` |
| Token 管理 | `backend/app/saihu/token.py` |
| 异常定义 | `backend/app/core/exceptions.py` |
| 时区处理 | `backend/app/core/timezone.py` |
| 路由入口 | `frontend/src/router/index.ts` |
| 主布局 | `frontend/src/components/AppLayout.vue` |
| 设计令牌 | `frontend/src/styles/tokens.scss` |
| 统一页面容器 | `frontend/src/components/PageSectionCard.vue` |

## 附录 B：环境变量速查

**后端** (`backend/.env`)：
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
SAIHU_BASE_URL=https://openapi.sellfox.com
SAIHU_CLIENT_ID, SAIHU_CLIENT_SECRET
LOGIN_PASSWORD, JWT_SECRET（至少 32 字节，建议 64 字节随机值）, JWT_EXPIRES_HOURS=24
PROCESS_ENABLE_WORKER=true
PROCESS_ENABLE_REAPER=true
PROCESS_ENABLE_SCHEDULER=true
WORKER_LEASE_MINUTES=2
WORKER_HEARTBEAT_SECONDS=30
REAPER_INTERVAL_SECONDS=60
```

**前端** (`frontend/.env`)：
```
VITE_API_PROXY_TARGET=http://localhost:8000
```

---

## 变更记录

| 日期 | 变更 | 相关 PROGRESS 章节 |
|---|---|---|
| 2026-04-24 | 安全库存采购-only 项保留到采购建议：无补货国家命中但 `purchase_qty > 0` 时保留 SKU，补货字段清空且采购/补货计数继续独立 | §3.63 |
| 2026-04-24 | 前端当前补货页与历史详情弹窗不再展示补货日期；`restock_dates` 仍保留在后端、快照与补货 Excel 导出中 | §3.62 |
| 2026-04-24 | 需求日期口径改为需求截止日期：runner 按 `restock_dates[country] <= demand_date` 保留补货国家，过期未处理国家纳入截止范围，前端与 Excel 元信息同步改为“需求截止日期” | §3.61 |
| 2026-04-24 | 移除采购日期 `purchase_date`：step6 仅输出 `urgent` / `restock_dates`，采购快照与采购 Excel 不再保存或展示采购日期，采购页同步删除“仅显示紧急（≤30天）”筛选 | §3.59 |
| 2026-04-23 | 引擎采购口径调整：`buffer_days` 作为国内仓备货时间参与 `purchase_date`，不再参与 `purchase_qty`；采购量只叠加安全库存天数 | §3.54 |
| 2026-04-22 | Audit Stage 3 P0 闪电修：engine step4 clamp `purchase_qty >= 0` + DB CheckConstraint；`docs_enabled()` production 硬关忽略 env；CI 加 postgres service 让 integration tests 真跑；`.gitignore` 补 `*.exe` / `*.lnk` 防误 commit | PROGRESS.md 最近更新 |
| 2026-04-21 | 采购/补货分拆 + 安全库存 + EU 合并 + 嵌套 Tab 视图 | §3.53 |
| 2026-04-20 | Full audit 收口修复（并发保护 / 查询口径 / fail-close 探测 / dev 重建稳定性） | §3.52 |
| 2026-04-19 | Plan A 后端 + 前端：推送赛狐 → Excel 导出 + Snapshot 版本化 | §3.49 / §3.50 / §3.51 |
| 2026-04-17 及之前 | 权限系统 / 审计改造 / 数据同步基础 | §3.44 及之前 |

本表只列架构级变更；小改动以 `PROGRESS.md` 各节为准。

---

**本架构蓝图应随架构演进同步更新。** 若发现文档与代码实际行为不符，以代码为准并回填文档。
