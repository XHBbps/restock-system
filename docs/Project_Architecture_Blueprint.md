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
│  │ （已移除旧赛狐写入模块；见 §3.6 导出快照子系统）            │ │
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
| 1 | `step1_velocity.py` | 近 30 天订单处理列表订单 | `velocity[sku][country]` | 加权日均销量：7日×0.5 + 14日×0.3 + 30日×0.2；仅消费 `source='订单处理'` 且 `package_status!='has_canceled'` 的包裹订单；若 `global_config.restock_regions` 非空，仅这些国家参与补货国家维度计算 |
| 2 | `step2_sale_days.py` | 库存 + 在途 + velocity + SKU 映射规则 | `sale_days[sku][country]` | `(available + reserved + in_transit) / velocity`；启用映射规则会先在同仓库、同组件 SKU 维度按该国家 velocity 分配共享库存，再按组合短板换算商品 SKU 视角库存，跨组合替代方案求和；velocity≤0 跳过 |
| 3 | `step3_country_qty.py` | velocity + 库存 + 有效目标库存天数 | `country_qty[sku][country]` | `effective_target_days = target_days + max(demand_date - today, 0)`；`max(0, ceil(effective_target_days × velocity - (available + reserved + in_transit)))` |
| 4 | `step4_total.py` | country_qty + velocity + 国内库存 + safety_stock_days | `purchase_qty[sku]` | `max(0, Σcountry_qty − (local.available + local.reserved) + ceil(Σvelocity × safety_stock_days))`；`Σcountry_qty` 使用 Step 3 的补货日期口径，`Σvelocity` 覆盖所有国家，不受 `restock_regions` 限制；`buffer_days` 不参与采购量 |
| 5 | `step5_warehouse_split.py` | country_qty + 有效包裹订单 + 订单头邮编 + 邮编规则 + 国家规则仓映射 | `warehouse_breakdown[country][wh_id]` | 样本来自 `source='订单处理'` 且 `package_status!='has_canceled'` 的包裹订单，样本数量为 `max(quantity_shipped - refund_num, 0)`；邮编优先读取 `order_header.postal_code`；按邮编规则分配到具体仓库，已知部分按命中比例分配，未知部分按该国家已配置邮编规则的仓均分；仅规则仓参与分仓与均分兜底；若无规则仓则该国家不分仓；若配置 `restock_regions`，仅消费这些国家的订单作为分仓依据；同优先级 tied 均分；整数分配使用 floor + 最大余数法，保证仓内合计等于国家补货量 |
| 6 | `step6_timing.py` | sale_days + lead_time + country_qty | `urgent` + `restock_dates` | `urgent` 仍按任一正补货国家 `sale_days <= lead_time_days`；`restock_date[sku][country] = today + int(sale_days[sku][country]) − lead_time_days`，仅对正补货国家输出，缺少 sale_days 时记为 `null` |

**运行上下文**：`EngineContext` 包含 `target_days`、`buffer_days`、`lead_time_days`、`safety_stock_days`、`restock_regions`、`eu_countries` 和本次请求的补货日期 `demand_date`。runner 会计算 `demand_days=max(demand_date - today, 0)` 并传给 Step 3 形成有效目标库存天数；`buffer_days` 作为全局配置快照保留，但当前仅用于追溯，不参与 `purchase_qty` 或 `restock_dates` 计算；`restock_regions` 保存前会走统一国家码标准化，`UK` 等别名按 ISO 代码去重为 `GB`；`global_config.eu_countries` 由同步层消费，保存该配置且实际变化时会同步回填历史订单、库存与在途国家码，`global_config_snapshot` 会冻结这些全局参数与 `demand_date` 以便追溯。

**SKU 映射转换层**：`backend/app/engine/sku_mapping.py` 只在计算读取阶段消费 `sku_mapping_rule` / `sku_mapping_component`，不会改写同步落库的 `inventory_snapshot_latest`、`in_transit_record` 或库存明细展示。`sku_mapping_component.group_no` 表示替代组合编号：同一 `commodity_sku` 下相同 `group_no` 的组件是 AND，不同 `group_no` 是 OR。`A=2*B` 按同仓库 `floor(B/2)` 计算，`A=1*B+2*C` 按同仓库 `min(floor(B/1), floor(C/2))` 计算，`A=B 或 C 或 D` 按同仓库各单组件组合可组装数求和，`A=B+C+D 或 E+F+G` 则两个组合分别取最小组件数后求和；组件不能跨仓库、跨国家组合。不同商品规则可以共享同一个库存 SKU，计算时先在每个仓库、每个共享组件 SKU 内按启用商品规则分配组件库存，避免重复计入；Step 2 使用仓库所在国家的 `velocity[sku][country]` 作为分配权重，Step 4 使用 SKU 全国家 velocity 合计作为本地仓分配权重，若任一共享商品没有正销量信号则该组件在共享商品间均分。Step 2 会把海外仓库存和有目标仓库 ID 的组件在途合并后按上述规则计算可组装数量，再按国家汇总到商品 SKU；Step 4 会按国内仓同仓库组件库存按上述规则计算可组装数量，再汇总为本地商品 SKU 库存。停用规则保留但不参与计算；未映射且不等于商品 SKU 的库存 SKU 不进入补货计算。

**持久化**：一次完整计算在事务内执行，受 `pg_advisory_xact_lock(7429001)` 保护；runner 不再按 `restock_dates[country] <= demand_date` 过滤补货国家，补货国家是否进入本次建议只由 Step 3 的正补货量与 `restock_regions` 白名单决定。若 `purchase_qty <= 0` 且国家补货合计为 0，则跳过该 SKU；若仅安全库存触发采购但无国家补货量，仍保留为采购-only 条目，并保持 `country_breakdown` / `warehouse_breakdown` / `allocation_snapshot` / `restock_dates` 为空、`total_qty=0`、`urgent=false`；若无条目则返回 `None`，不归档旧 `draft`、不关闭生成开关、不生成空建议单；成功生成非空建议单后才归档旧 `draft`，写入 `suggestion` / `suggestion_item`，统计 `procurement_item_count`、`restock_item_count`，并由 `calc_engine_job` 将 `global_config.suggestion_generation_enabled` 自动翻 OFF。

**快照字段**：`velocity_snapshot`、`sale_days_snapshot`、`allocation_snapshot`、`global_config_snapshot` 均以 JSONB 保存；其中 `velocity_snapshot` / `sale_days_snapshot` 保留完整 SKU 追溯数据，`global_config_snapshot.demand_date` 记录业务补货日期；`suggestion_item.purchase_qty` 用于采购视图，`country_breakdown` / `warehouse_breakdown` 用于补货视图，`restock_dates` 用于追溯、紧急程度判断与 Excel 导出（前端当前列表不展示）。

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

**商品主数据同步**：`sync_product_listing` 是商品同步统一 job。它先通过 `backend/app/saihu/endpoints/commodity.py` 调用赛狐 SKU 主数据接口 `/api/commodity/pageList.json`，不传 `state` 或 `isGroup` 过滤，按 `sku` UPSERT 到 `commodity_master`；随后继续调用在线产品 listing 接口 `/api/order/api/product/pageList.json` 写入 `product_listing`，保留店铺、站点、sellerSku 与近 7/14/30 天销量用于商品页展开明细。同步过程中只为新发现 SKU 补建 `sku_config(enabled=false)`，不覆盖已有 `enabled`、`lead_time_days`，商品状态 `state` 仅作展示/筛选信息，不自动影响补货计算。`run_engine` 仍只消费 `sku_config.enabled=true` 的 SKU。

**EU 国家归一化与新国家发现**：同步层写入订单、商品、库存、出库在途数据时，会按 `global_config.eu_countries` 将成员国映射为字面值 `EU`，并在对应 `original_*` 字段保留原国家码。进入国家选项、成员国配置和补货区域配置的国家码先执行 `trim + uppercase + 两位字母校验 + 别名标准化`，当前 `UK` 统一标准化为 ISO 代码 `GB`。订单处理列表只读取响应顶层 `marketplace` 作为国家来源；该值缺失或无法识别时写 `ZZ` 并记录结构化日志，不再从地址、店铺名或平台名猜测国家；有效国家码若属于 `eu_countries` 则归并为 `EU` 并在 `original_country_code` 保存原码。全局配置接口保存 `eu_countries` 且实际变化时，会在同一事务内调用 `backfill_eu_country_mapping()` 回填本地历史 `order_header`、`inventory_snapshot_latest`、`in_transit_record`：源国家优先取各表 `original_*` 字段，否则取当前国家字段，并先按同一别名表标准化；源国家属于当前 EU 集合时写映射后国家为 `EU` 且 `original_* = 标准化源国家`，否则恢复为标准化源国家并清空 `original_*`。该回填只改本地库，不调用赛狐 API。

**动态国家选项**：`GET /api/config/country-options` 汇总内置常见国家与数据库已观测国家，观测来源包括订单 `country_code/original_country_code`、仓库 `country`、库存 `country/original_country`、出库 `target_country/original_target_country`。观测值会先走统一标准化，因此历史 `UK` 只会以 `GB` 输出；接口返回 `builtin`、`observed`、`can_be_eu_member` 与 `unknown_country_codes`，前端订单、库存、出库、仓库、邮编规则、补货区域和 EU 成员国配置均消费该接口；EU 成员国配置不允许 `EU` 与 `ZZ`。内置国家名包含 `GB - 英国`、`CZ - 捷克`、`RO - 罗马尼亚`，以及订单处理列表新观测到的 `AT - 奥地利`、`CH - 瑞士`、`CY - 塞浦路斯`、`DK - 丹麦`、`EE - 爱沙尼亚`、`FI - 芬兰`、`LT - 立陶宛`、`LV - 拉脱维亚`、`MT - 马耳他`、`SI - 斯洛文尼亚`。

**国家时区约束**：`backend/app/core/timezone.py` 的 `country_to_tz()` 会先执行同一国家码别名标准化，因此 `UK` 使用 `GB` 的 `Europe/London`。除 `EU`、`ZZ` 这类非真实国家外，`BUILTIN_COUNTRY_NAMES` 的所有内置国家必须在 `COUNTRY_TO_TIMEZONE` 中配置 IANA 时区；对应单元测试作为防漏 tripwire。仍只是观测到但未内置的未知二字码会回退北京时间，并记录结构化 warning。

**订单处理列表同步**：`sync_order_list` 是订单同步唯一后台任务入口，只调用赛狐订单处理列表 `/api/packageShip/v1/getPackagePage.json`。请求使用 `purchaseDateStart/purchaseDateEnd`，窗口为任务开始时间向前回退 12 个日历月到当前开始时间，`pageSize=200`，并按全局店铺同步模式传 `shopIdList`。列表响应中的包裹统一落入 `order_header` / `order_item`，`source='订单处理'`，`order_platform=platformName`，`shop_name=shopName`，`package_sn/package_status/postal_code` 保存在订单头；`postal_code` 仍来自 `address.postalCode`，但冲突更新时若本次响应邮编为空或 `address` 缺失，不覆盖已有 `order_header.postal_code`；`country_code/original_country_code` 来自顶层 `marketplace`，空值或非法值写 `ZZ`。同一 `amazonOrderId` 拆成多个 `packageSn` 时以 `shop_id + amazon_order_id + source + package_sn` 唯一定位。包裹内 `orders` 生成订单头，`items` 按 `items.amazonOrderId` 归属订单，`items.commoditySku` 写入 `order_item.commodity_sku`，不使用 `sellerSku` 作为商品 SKU；`items.quantityOrdered` 同时写入 `quantity_ordered` 与 `quantity_shipped`，`refund_num=0`。同步前会清理旧 `source in ('亚马逊','多平台')` 的订单头、明细、详情和详情抓取日志，避免新旧来源重复计算。

**出库记录同步**：`sync_out_records` 会把赛狐“其他出库”记录同步到 `in_transit_record` / `in_transit_item`，除在途状态观测所需字段外，还保留 `warehouseId`、`updateTime`、`type/typeName`、`commodityId`、`perPurchase`，用于数据页直接展示“出库”主表和明细表字段。`target_country` 改为从备注文本提取国家名（如 `20260410美国-赢捷-加州-散货-在途中` → `US`）；提取失败时保持空值，不再回退到 `targetFbaWarehouseId -> warehouse.country`。每次执行该同步任务后，还会顺带扫描历史 `target_country` 为空的旧记录并按同一备注规则回填，不覆盖已有值。

**旧订单详情抓取链路删除**：订单处理列表已经包含补货计算所需的订单、SKU、国家、邮编和包裹状态，因此自动 `sync_order_detail`、手动 `refetch_order_detail`、订单页“详情获取”入口、旧订单详情 job 模块和旧赛狐订单 endpoint 封装均已删除。`order_detail` 与 `order_detail_fetch_log` 作为历史表保留，切换到订单处理列表后不再作为新订单来源的依赖。

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

**自动调度规则**：`sync_shop` 每日 03:00 入队，`sync_warehouse` 每日 03:30 入队，`daily_archive` 每日 02:00 入队，`retention_purge` 每日 04:00 入队，`retry_failed_api_calls` 每 5 分钟入队；`sync_product_listing`、`sync_inventory`、`sync_out_records`、`sync_order_list` 按 `global_config.sync_interval_minutes` 间隔入队。`GET /api/sync/scheduler` 由 API 进程提供状态，即使 API 进程本身不启动 APScheduler，也会基于 job trigger 推导下次执行时间；真正入队仍只发生在 `PROCESS_ENABLE_SCHEDULER=true` 的 scheduler 进程。

**进度追踪**：`TaskRun.current_step / step_detail / total_steps / result_summary` 由 worker 在执行中写入，前端 `TaskProgress` 组件轮询 `/api/tasks/{id}`。`calc_engine` 在生成成功或无需求时写结构化 JSON 摘要（`generated`、`suggestion_id`、`demand_date`、可选 `reason`）；店铺、仓库、商品、库存、订单、出库等分页同步任务复用赛狐分页响应里的 `totalPage` 输出“第 P / N 页”进度，不额外发起预扫描请求。自 2026-04-20 起，worker 的 heartbeat、进度更新和 success/failed 终态回写都带 `status='running' + worker_id` 条件；若租约已被 reaper 回收，则抛 `TaskLeaseLostError` 并停止继续覆盖状态。
**信息总览快照任务**：`refresh_dashboard_snapshot` 也是标准 TaskRun 任务，复用现有去重、轮询和失败回写机制；它在后台调用 `build_dashboard_payload()` 生成 `dashboard_snapshot` 单例缓存，页面刷新时优先消费该缓存而不是重复现算。
**失败调用重试任务**：`retry_failed_api_calls` 是标准 TaskRun job，由 APScheduler 每 5 分钟入队，使用默认 `dedupe_key=job_name` 避免并发；它只消费 `api_call_log` 中可精确还原的赛狐 `40019` 失败日志，重试前检查相关同步任务是否活跃，活跃则跳过等待下一轮。
**任务权限注册表**：`app/tasks/access.py` 统一维护 TaskRun 作业清单，以及查看/操作权限映射；通用 `POST /api/tasks` 只允许创建显式白名单里的任务。旧赛狐写入作业已随 §3.6 的导出快照子系统一同删除。

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
- **自动队列**：最终仍为 `40019` 且已保存 `request_payload` 的原始调用会进入 `retry_failed_api_calls` 队列；自动任务按 `endpoint + request_payload` 精确重放，子调用通过 `retry_source_log_id` 关联原失败日志，不再扩展为整类同步任务。

**限流**：
```python
_ENDPOINT_RATE_OVERRIDES = {}
# 默认 1 QPS per endpoint；旧订单详情接口不再有特殊 QPS 覆盖
```

`retry_failed_api_calls` 在客户端 limiter 之外再按更保守间隔重放：当前默认 1 QPS endpoint 间隔 1.5 秒。订单处理列表接口 `/api/packageShip/v1/getPackagePage.json` 属于 `sync_order_list`，自动重试时的忙碌任务映射为 `sync_order_list` / `sync_all`；旧订单列表、旧多平台订单和旧订单详情接口不再映射到自动重试任务。

`/api/commodity/pageList.json` 与 `/api/order/api/product/pageList.json` 都归属 `sync_product_listing`，因此 `40019` 精确重试会在商品同步或全量同步活跃时跳过，避免同一商品分页接口并发重放。

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

**RBAC 权限语义**：权限码注册表位于 `backend/app/core/permissions.py`。角色权限保存入口 `backend/app/api/auth_roles.py` 会调用 `expand_permission_dependencies()`，将同一命名空间内的操作类权限（`edit`、`operate`、`manage`、`delete`、`export`、`refresh`、`new_cycle`）自动补齐对应 `view` 权限，保证能执行操作的角色也能进入对应页面或读取必要数据。`GET /api/auth/roles/{role_id}/permissions` 返回的是角色有效权限集合；超管角色不依赖 `role_permission` 显式关联，读取时返回全部 active 权限码，写入仍被拒绝。权限集合未发生实际变化时不重写关联表，也不 bump `sys_user.perm_version`。

### 3.6 导出快照子系统（app/services + app/api/snapshot.py）

**定位**：取代旧赛狐写入链路，改为“建议单 → 用户勾选采购/补货条目 → 生成不可变 Snapshot + Excel 文件 → 用户下载”的工作流。采购与补货从 API、快照版本、条目导出状态和 Excel 格式上完全拆分。

**核心表**：

| 表 | 职责 | 关键字段 |
|---|---|---|
| `suggestion_snapshot` | 一次导出即一个 snapshot；冻结 `snapshot_type`、`version`、`exported_by`、`exported_from_ip`、`global_config_snapshot`、`item_count`、`generation_status`、`file_path`、`file_size_bytes`、`download_count` | FK `suggestion_id`，`UNIQUE(suggestion_id, snapshot_type, version)` |
| `suggestion_snapshot_item` | snapshot 冻结的条目副本；采购快照保存 `purchase_qty`，补货快照保存 `total_qty` / `country_breakdown` / `warehouse_breakdown` / `restock_dates` | FK `snapshot_id` ON DELETE CASCADE |
| `suggestion_item` | 当前 draft 可编辑条目；采购导出状态与补货导出状态独立 | `purchase_qty` 供采购视图；`country_breakdown` / `warehouse_breakdown` 供补货视图；`restock_dates` 供追溯、紧急程度判断与 Excel 导出；`procurement_export_status` / `procurement_exported_snapshot_id` / `procurement_exported_at`，`restock_*` 同构 |

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
5. `excel_export.py` 根据类型生成不同工作簿：采购为“主数据 + 采购明细”，补货为“主数据 + SKU汇总 + SKU×国家 + SKU×国家×仓库”；“主数据”记录 `global_config_snapshot.demand_date` 对应的“补货日期”，采购/补货明细表不增加补货日期列；补货工作簿在国家与仓库明细中导出 `restock_dates` 对应的“补货日期”，前端当前补货视图不展示 `restock_dates`。
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
- **字体**：当前补货日期版本仍引用 Google Fonts；生产 `deploy/Caddyfile` 临时放行 `fonts.googleapis.com` / `fonts.gstatic.com`，长期建议改为自托管或系统字体栈
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
| `config.ts` | `GlobalConfig` 暴露 `safety_stock_days`、`eu_countries`、`restock_regions` 等现行字段；`CountryOptionsResponse` 封装 `GET /api/config/country-options` 的动态国家选项；`GenerationToggle` 暴露 `can_enable` / `can_enable_reason` |
| `engine.ts` / `task.ts` | 手动触发必填补货日期字段 `demand_date` 的 `POST /api/engine/run`；`task.ts` 同时封装 `getTask()` 与 `listTasks()`，当前建议页会分别查询 `calc_engine` 的 `pending` / `running` 任务以复用进度 |

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
- `DataOrdersView.vue`：订单列表按页返回，并仅对当前页补查 `item_count` / `has_detail`；页面不展示来源和包裹号，也不按包裹号搜索；平台以标签展示，店铺仅显示名称；详情接口默认限定 `source='订单处理'`，前端仅保留 `package_sn` 作为内部精确定位参数
- `HistoryView.vue`：建议单历史页直接消费 `GET /api/suggestions` 的 `items/total/page/page_size`；状态列使用 `getSuggestionDisplayStatusMeta(status, snapshot_count)` 派生 4 档显示标签（`未提交 / 已导出 / 已归档 / 异常`），状态下拉对应后端 `display_status=pending|exported|archived|error`，由后端统一按 `snapshot_count` 派生过滤，避免前端只过滤当前页造成 `items` 与 `total` 错位；`canDelete(row)` 规则为 `row.snapshot_count === 0`。派生逻辑定义在 `frontend/src/utils/status.ts::deriveSuggestionDisplayStatus`，`SuggestionListView` 与 `SuggestionDetailView` 的状态 tag 共用该函数，避免多处硬编码映射。
- `DataProductsView.vue`：商品页通过 `listSkuOverview()` 下推 SKU、商品名、启用状态和分页参数；`/api/data/sku-overview` 以 `commodity_master + sku_config` 为主，商品名、图片、状态、组合标识、采购周期优先取商品主数据，listing 仅作为展开明细和销量参考，无 listing 的 SKU 仍可展示
- `DataInventoryView.vue`：库存页通过 `GET /api/data/inventory/warehouse-groups` 做仓库分组分页，保持仓库展开明细交互；库存明细的 `is_package` 由“是否存在商品主数据 SKU、在线 listing 商品 SKU 或 SKU 映射组件库存 SKU”实时派生，前端按“全部 / 未匹配 / 已匹配”展示筛选
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

**前端监控命名约定**：
- `src/utils/monitoring.ts` 统一负责监控页的名称展示口径，包括赛狐接口 `endpoint`、性能监控 `request/resource` 名称中文化，以及 tooltip 中保留原始路径
- `ApiMonitorView`、`PerformanceMonitorView`、`sync/FailedApiCallTable` 只消费该工具，不在页面内各自维护映射表，避免图表、表格、tooltip 口径漂移

**信息总览页口径**：
- `WorkspaceView` 首行卡片展示补货概览：`restock_sku_count` 为按当前补货引擎口径计算后 `total_qty > 0` 的启用 SKU 数，`no_restock_sku_count` 为其余启用 SKU 数，`risk_country_count` 表示当前快照中按 `restock_regions` 过滤后进入风险分层的国家数
- 左图使用分组柱状图展示各国缺货风险分布，统计对象是实时计算后写入 `dashboard_snapshot.payload.country_risk_distribution` 的 SKU+国家数量，而不是当前建议单快照；若 `restock_regions=[]` 则展示全部国家，若配置为 `["EU"]` 则只展示 `EU`
- “急需补货SKU”列表同样使用快照中的国家级 `sale_days`，并与风险分布使用同一 `restock_regions` 过滤口径；一行只表示一个 SKU 在一个国家上的风险，不再按 SKU 聚合
- 右图继续使用饼图，数据仍为 `country_restock_distribution`，即当前建议单全部条目的 `country_breakdown` 汇总，用于展示实际建议补货量的国家分布

**建议单与全局配置视图职责**：

| 视图 | 职责 |
|---|---|
| `SuggestionListView` | 顶部 `PageSectionCard.actions` 展示生成开关只读状态 tag 与当前建议 `补货日期`；发起区使用默认空的补货日期选择器，提交前校验空值与早于北京时间今天；`loadToggle()` + `loadActiveEngineTask()` 在 `onMounted` / `onActivated` 双钩子刷新开关与活跃 `calc_engine` 任务，活跃任务存在时复用 `TaskProgress` 并禁用日期选择器与生成按钮。列表页已收敛为生成与导出视角，不再保留旧赛狐写入时代的选择列、批量动作和状态筛选死代码。 |
| `SuggestionDetailView` | 勾选 `export_status='pending'` 的条目 → “导出 Excel”按钮走一步式 `POST /api/suggestions/{id}/snapshots` + `GET /api/snapshots/{id}/download` blob 流程（失败时仍在 `finally` 中 `await load()` 刷新快照历史，并区分”导出成功但下载失败”的独立错误文案）；右侧新增”历史快照区”`PageSectionCard`（6 列，按 `version` 降序，可重复下载）；导出前会先探测生成开关，探测失败时按 fail-close 禁用按钮；`SkuCard` 停止传入 `:blocker`（组件 prop 仍保留但所有调用点不再传值）；条目 `isEditable` 改为 `export_status !== 'exported'`（对应 snapshot 条目不可变的约束，见 §9.5 Don'ts）。 |
| `GlobalConfigView` | 新增”生成开关卡片”：`el-switch` 即时保存，翻 ON 时弹 `ElMessageBox` 二次确认”将归档全部 draft”，`PATCH` 失败时回滚开关状态并提示；无 `config:edit` 时控件只读并提示”无权限操作此开关”。 |
| `SkuMappingRuleView` | 位于“设置 > 基础配置 > 映射规则”，通过 `GET /api/config/sku-mapping-rules` 服务端分页、搜索商品 SKU / 库存 SKU、按启用状态筛选；支持新增、编辑、启停、删除、Excel/CSV 导入与 Excel 导出；编辑器按 `group_no` 展示“方案”，公式预览用 `或` 连接替代组合。 |
| `HistoryView` | 参见 §4.5 — 状态筛选 3 项，快照数 + 导出状态列，`canDelete` 基于 `snapshot_count === 0`。 |

---

## 5. 数据流程示例

### 场景 1：用户触发采补计算

```text
用户选择补货日期并点击“生成采补建议”
  ↓
POST /api/engine/run { demand_date: "YYYY-MM-DD" }
  ↓
api/sync.py: 校验补货日期不早于北京时间今天，enqueue_task("calc_engine", "manual")
  ↓
task_run 表 INSERT status=pending, dedupe_key="calc_engine"
  ↓
worker 抢占任务 → calc_engine_job
  ↓
run_engine 读取 global_config：target_days / buffer_days / lead_time_days / safety_stock_days / restock_regions / eu_countries，并读取 payload.demand_date 作为补货日期
  ↓
pg_advisory_xact_lock(7429001)
  ↓
6 步流水线：velocity → sale_days → country_qty（使用 target_days + demand_days）→ purchase_qty → warehouse_split → urgent/restock_dates
  ↓
按正补货量与采购量生成 suggestion_item；若无补货量且无采购量则返回 no_suggestion_needed
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
| `global_config` | 全局配置单行表；包含 `target_days`、`buffer_days`、`lead_time_days`、`safety_stock_days`、`restock_regions`、`eu_countries`、`suggestion_generation_enabled`、`generation_toggle_updated_by / generation_toggle_updated_at`、同步与登录配置 | `CHECK id=1`；`safety_stock_days` 范围 1–90；`restock_regions=[]` 表示全部国家参与补货计算；`eu_countries` 保存和读取时标准化 ISO 二字码别名，并拒绝 `EU` 与 `ZZ` |
| `commodity_master` | 赛狐 SKU 主数据 | 主键 `sku`；保存 `commodity_id/name/state/is_group/img_url/purchase_days/child_skus/last_sync_at`；仅作为商品展示、搜索和库存匹配依据，不直接决定是否进入补货计算 |
| `sku_config` | SKU 启用 / 禁用与业务参数 | `commodity_sku` 唯一 |
| `sku_mapping_rule` | 商品 SKU 到库存包裹 SKU 的映射规则 | `commodity_sku` 唯一；`enabled=false` 时规则保留但不参与引擎 |
| `sku_mapping_component` | 映射规则组件行 | `rule_id + inventory_sku` 唯一；允许不同商品规则共享同一 `inventory_sku`；`group_no > 0`；`quantity > 0`；同一 `group_no` 内多行表示 AND 组合，不同 `group_no` 表示 OR 替代方案 |
| `warehouse` | 海外仓/国内仓基础资料 | `country` 可为空；变更仓库国家会级联更新库存最新快照口径 |
| `order_header` / `order_item` | 订单头与订单明细 | `order_header.source='订单处理'` 为当前订单来源，`order_platform` 保存平台名，`package_sn/package_status/shop_name/postal_code` 保存订单处理列表包裹字段；`UNIQUE(shop_id, amazon_order_id, source, package_sn)` 支持同订单拆包；`country_code` 保存映射后国家，`original_country_code` 保存 EU 合并前国家；按 `shop_id + purchase_date`、`order_status + purchase_date`、`package_status + purchase_date` 建索引 |
| `order_detail` / `order_detail_fetch_log` | 历史订单详情与拉取日志 | 作为切换前亚马逊订单详情历史表保留；当前订单处理列表同步不再写入或依赖该表 |
| `product_listing` | 赛狐在线产品信息 | `marketplace_id` 保存映射后 2 字符国家码或 `EU`，`original_marketplace_id` 保存 EU 合并前国家 |
| `inventory_snapshot_latest` | SKU × 仓库最新库存 | `country` 保存映射后国家，`original_country` 保存 EU 合并前国家；`warehouse_id + commodity_sku` 唯一 |
| `in_transit_record` / `in_transit_item` | 出库 / 在途记录与明细 | `target_country` 保存映射后国家，`original_target_country` 保存 EU 合并前国家 |
| `suggestion` | 建议单头 | `status IN ('draft','archived','error')`；`procurement_item_count` / `restock_item_count` 分别统计采购与补货需求 SKU 数 |
| `suggestion_item` | 当前建议条目 | `purchase_qty` 供采购视图；`country_breakdown` / `warehouse_breakdown` 供补货视图；`restock_dates` 供追溯、紧急程度判断与 Excel 导出；采购与补货各自拥有 `*_export_status`、`*_exported_snapshot_id`、`*_exported_at` |
| `suggestion_snapshot` | 导出快照头（§3.6） | `snapshot_type IN ('procurement','restock')`；`UNIQUE(suggestion_id, snapshot_type, version)`；`generation_status IN ('generating','ready','failed')` |
| `suggestion_snapshot_item` | 导出快照条目副本 | FK `snapshot_id` ON DELETE CASCADE；冻结 `purchase_qty`、`restock_dates` 与补货拆分 JSONB |
| `excel_export_log` | Excel 下载审计 | 记录 snapshot、操作者、IP、User-Agent、文件大小等 |
| `task_run` | 后台任务队列 | `dedupe_key + active status` partial unique index |
| `dashboard_snapshot` | 信息总览缓存快照 | 单例缓存 dashboard payload、刷新状态与错误信息 |
| `api_call_log` | 赛狐 API 调用日志与 40019 重试队列 | `request_payload` 保存原始请求；`retry_status` 区分 `queued/resolved/permanent/unsupported`；`retry_source_log_id` 关联自动重试子日志 |
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
- `ix_api_call_log_retry_queue`：加速 `retry_failed_api_calls` 扫描 `40019 + queued + request_payload` 的原始失败日志
- `ix_suggestion_item_urgent`：仅索引紧急条目

**JSONB 字段**：`country_breakdown`、`warehouse_breakdown`、`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot`、`allocation_snapshot`、`payload`、`request_payload`。其中 `global_config_snapshot` 会保留 `restock_regions` 等配置快照；`api_call_log.request_payload` 用于精确重放赛狐 `40019` 失败调用。当前仅整体读取，不查 JSONB 内部字段，无需 GIN 索引。

### 6.3 迁移管理

- 工具：Alembic（命名规范配置在 `db/base.py` 的 NAMING_CONVENTION）
- 位置：`backend/alembic/versions/`
- 命名：`YYYYMMDD_HHMM_description.py`
- 执行：`alembic upgrade head`（容器启动时由 deploy 脚本自动执行）
- 兼容约束：补货日期相关迁移链路的当前 head 为 `20260425_1420`；该 revision 是生产兼容 marker，不修改 schema，仅用于兼容已经推进到 `20260425_1420` 的生产库。

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

### ADR-6：旧赛狐写入去重决策（已废弃）

- **Status**: Superseded by Plan A 2026-04-19（见 §3.6 / PROGRESS.md §3.49）。旧赛狐写入链路已整体删除，本 ADR 的原始决策不再有效，仅保留做审计追溯。
- **Replacement decision**：`load_in_transit` 改回直接读取赛狐同步下来的在途出库记录（`in_transit_record` + `in_transit_item`，按 `is_in_transit=true` 过滤），不再做跨批次旧建议数量冲销。业务人员通过 Excel 导出 + 线下落单的工作流替代了即时去重诉求；如果需要防止重复下单，现在依靠“首次导出后翻 OFF 生成开关 → 新周期由业务人员显式翻 ON 并归档旧 draft”这一闸门，而不是引擎层的数量冲销。
- **原始决策（已失效）**：`load_in_transit` 从旧建议条目汇总数量，而非查赛狐在途
- **原始驱动（已失效）**：
  - 赛狐在途数据有同步延迟（需要下次 sync 才写入本地）
  - 旧建议单立即可查，0 延迟去重
- **原始约束（已失效）**：只考虑近 90 天的旧建议（避免累积过多历史数据）

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
- **新增独立 job**：例如“补货提醒”作为独立 task，读取 `suggestion_item` 后发送通知

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
- **docs/**：保留当前事实文档、架构蓝图、部署指南、运维手册和入门说明
- **本文档**：架构层级的真理源（Source of Truth）

### 12.2 架构变更流程

1. 先讨论设计，明确范围、取舍和验收口径
2. 如需落盘设计材料，使用当前任务明确指定的位置
3. 用户审阅通过
4. 生成可执行计划
5. 按计划执行
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
| 2026-05-03 | 订单同步切换为订单处理列表 `/api/packageShip/v1/getPackagePage.json`；`order_header` 新增包裹字段并调整唯一键；Step 1 / Step 5 只消费非已作废包裹；旧订单详情 job 与旧订单 endpoint 封装删除，历史表保留 | PROGRESS.md §3.91 / §3.92 |
| 2026-05-03 | 订单处理列表国家改为读取顶层 `marketplace`，空值或非法值写 `ZZ`；订单页移除来源和包裹号展示/搜索，平台改为标签，店铺仅显示名称 | PROGRESS.md §3.94 |
| 2026-05-03 | 补齐订单处理列表新观测国家 `AT/CH/CY/DK/EE/FI/LT/LV/MT/SI` 的中文 label 与 IANA 时区；`ZZ` 只在赛狐包裹列表缺失可识别 `marketplace` 时写入，不按地址、店铺名或平台名猜测国家 | PROGRESS.md §3.93 |
| 2026-05-03 | SKU 映射组件允许跨商品规则共享，`sku_mapping_component` 唯一约束从 `inventory_sku` 收窄为 `rule_id + inventory_sku`；Step 2 按仓库国家 velocity 分配共享组件库存，Step 4 按全国家 velocity 合计分配，本规则内重复组件仍被拒绝 | PROGRESS.md §3.90 |
| 2026-05-03 | 商品同步接入赛狐 SKU 主数据 `/api/commodity/pageList.json`，新增 `commodity_master` 表；`sync_product_listing` 先同步主数据再同步 listing，新发现 SKU 默认 `enabled=false`；商品页和库存匹配改用主数据口径 | PROGRESS.md §3.89 |
| 2026-05-02 | SKU 映射规则支持替代组合：`sku_mapping_component.group_no` 同组 AND、跨组 OR，Step 2/Step 4 按仓库内各组合可组装数求和，导入导出模板新增“组合编号”并兼容旧模板 | PROGRESS.md §3.88 |
| 2026-04-30 | Step 5 分仓样本改为订单详情左连接与净发货数口径；未知需求按国家规则仓均分后再与已知邮编分配结果合并 | PROGRESS.md §3.87 |
| 2026-04-29 | 角色权限保存新增操作权限隐含查看权限补齐；无实际权限变化时不重写关联表、不 bump `perm_version`；超管权限读取返回全部 active 权限码 | PROGRESS.md §3.85 |
| 2026-04-29 | Step 5 matched 分仓取整改为 floor + 最大余数法，订单列表同步在本次无有效明细时保留旧 item；赛狐示例凭据统一改为占位符 / 环境变量 | PROGRESS.md §3.84 |
| 2026-04-29 | 国家代码进入动态国家选项、EU 成员国配置、补货区域配置和多平台订单国家字段前统一标准化；历史别名 `UK` 输出与保存为 ISO 代码 `GB`；EU 配置变化会回填订单、库存与在途本地数据；内置国家必须配置时区 | PROGRESS.md §3.83 |
| 2026-04-29 | 订单列表同步成功水位改为本次亚马逊查询窗口 `date_end`；多平台订单 `purchase` 滚动窗口改为 6 个日历月 | PROGRESS.md §3.82 |
| 2026-04-28 | 国家选项改为“内置常见国家 + 数据库已观测国家”动态来源；新 2 位国家码按原码入库，EU 归类仍由管理员通过 `eu_countries` 维护，`EU` / `ZZ` 不可加入 EU 成员国 | PROGRESS.md §3.79 |
| 2026-04-27 | 同步日志 / 接口监控新增赛狐 `40019` 精确自动重试队列：保存 `request_payload`，每 5 分钟按原始请求重放，成功标记 `resolved`，最多 5 次后 `permanent` | §3.75 |
| 2026-04-27 | 库存明细新增未匹配标识与筛选：`is_package` 由 `product_listing.commodity_sku` 是否存在实时派生，前端展示为未匹配 / 已匹配，仓库分组统计随筛选口径重算 | §3.74 |
| 2026-04-27 | 新增 SKU 映射规则配置与补货计算转换层：同仓库组件库存按公式组装为商品 SKU 视角库存，库存明细仍保留原始 SKU 展示 | §3.76 |
| 2026-04-26 | 补货日期参与数量计算：`demand_date` 扩展 Step 3 有效目标库存天数，`restock_dates` 不再过滤补货国家，前端与 Excel 元信息统一展示“补货日期” | §3.71 |
| 2026-04-25 | 清理历史设计产物与旧赛狐写入残留配置，文档入口收敛到当前 `docs/` 事实文档 | §3.64 |
| 2026-04-24 | 安全库存采购-only 项保留到采购建议：无补货国家命中但 `purchase_qty > 0` 时保留 SKU，补货字段清空且采购/补货计数继续独立 | §3.63 |
| 2026-04-24 | 前端当前补货页与历史详情弹窗不再展示补货日期；`restock_dates` 仍保留在后端、快照与补货 Excel 导出中 | §3.62 |
| 2026-04-24 | 旧 `demand_date` 日期筛选：runner 曾按 `restock_dates[country] <= demand_date` 保留补货国家；该口径已由 2026-04-26 的补货日期数量计算取代 | §3.61 / §3.71 |
| 2026-04-24 | 移除采购日期 `purchase_date`：step6 仅输出 `urgent` / `restock_dates`，采购快照与采购 Excel 不再保存或展示采购日期，采购页同步删除“仅显示紧急（≤30天）”筛选 | §3.59 |
| 2026-04-23 | 引擎采购口径调整：`buffer_days` 作为国内仓备货时间参与 `purchase_date`，不再参与 `purchase_qty`；采购量只叠加安全库存天数 | §3.54 |
| 2026-04-22 | Audit Stage 3 P0 闪电修：engine step4 clamp `purchase_qty >= 0` + DB CheckConstraint；`docs_enabled()` production 硬关忽略 env；CI 加 postgres service 让 integration tests 真跑；`.gitignore` 补 `*.exe` / `*.lnk` 防误 commit | PROGRESS.md 最近更新 |
| 2026-04-21 | 采购/补货分拆 + 安全库存 + EU 合并 + 嵌套 Tab 视图 | §3.53 |
| 2026-04-20 | Full audit 收口修复（并发保护 / 查询口径 / fail-close 探测 / dev 重建稳定性） | §3.52 |
| 2026-04-19 | Plan A 后端 + 前端：旧赛狐写入链路 → Excel 导出 + Snapshot 版本化 | §3.49 / §3.50 / §3.51 |
| 2026-04-17 及之前 | 权限系统 / 审计改造 / 数据同步基础 | §3.44 及之前 |

本表只列架构级变更；小改动以 `PROGRESS.md` 各节为准。

---

**本架构蓝图应随架构演进同步更新。** 若发现文档与代码实际行为不符，以代码为准并回填文档。
