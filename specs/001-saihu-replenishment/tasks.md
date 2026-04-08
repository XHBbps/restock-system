---
description: "Task list for 赛狐补货计算工具 implementation"
---

# Tasks: 赛狐补货计算工具

**Input**: Design documents from `specs/001-saihu-replenishment/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Not explicitly requested. Critical paths (rule engine steps, saihu sign, zipcode matcher) MUST have unit tests per FR-012 Step 1–6 verifiability; extensive contract/integration tests are optional for other paths.

**Organization**: Tasks are grouped by user story. Each story is independently deliverable after the foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallel-safe (different files, no dependencies)
- **[Story]**: US1..US5 mapped to spec.md user stories
- Paths anchored at repo root

## Path Conventions
- Backend: `backend/app/**`
- Frontend: `frontend/src/**`
- Deploy: `deploy/**`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create top-level project structure: `backend/`, `frontend/`, `deploy/`, `.github/` per plan.md
- [X] T002 [P] Initialize backend Python project in `backend/pyproject.toml` with deps: fastapi, uvicorn[standard], sqlalchemy[asyncio], alembic, asyncpg, pydantic, pydantic-settings, httpx, aiolimiter, tenacity, apscheduler, structlog, passlib[bcrypt], python-jose[cryptography], python-dateutil
- [X] T003 [P] Add backend dev deps in `backend/pyproject.toml`: ruff, black, mypy, pytest, pytest-asyncio, pytest-cov, httpx (test client), freezegun
- [X] T004 [P] Configure backend tooling: `backend/pyproject.toml` `[tool.ruff]`, `[tool.black]`, `[tool.mypy]`, `[tool.pytest.ini_options]` with strict settings aligned to constitution; **additionally** wire up pre-commit hooks via `.pre-commit-config.yaml` running ruff + black + mypy on every commit (宪法 NON-NEGOTIABLE 要求每次提交即通过)
- [X] T005 [P] Initialize frontend Vue 3 project in `frontend/package.json` with deps: vue, vue-router, pinia, element-plus, axios, lucide-vue-next, dayjs; dev deps: vite, typescript, @vitejs/plugin-vue, vue-tsc, eslint, @typescript-eslint, prettier, sass, vitest
- [X] T006 [P] Configure frontend tooling: `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/eslint.config.js`, `frontend/.prettierrc.json`; **additionally** add `lint-staged` + husky 或 pre-commit 钩子跑 `eslint --max-warnings=0 && vue-tsc --noEmit` on every commit
- [X] T007 [P] Create Docker Compose stack in `deploy/docker-compose.yml` with services: caddy, db (postgres:16-alpine), backend, frontend; volumes for pg data + caddy data
- [X] T008 [P] Create `deploy/Caddyfile` with HTTPS + reverse proxy for `/api/*` → backend:8000, rest → frontend:80
- [X] T009 [P] Create `deploy/.env.example` and `backend/.env.example` with all required keys (DB, Saihu, JWT, login password)
- [X] T010 [P] Create backend `Dockerfile` (multi-stage: build deps → runtime) and frontend `Dockerfile` (build vue → nginx static)
- [X] T011 [P] Create `.gitignore`, `.editorconfig`, `.dockerignore` at repo root

**Checkpoint**: Project scaffolding ready, `docker compose config` passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: Complete this entire phase before starting any user story.

### Backend core (config, logging, DB session)

- [X] T012 Create `backend/app/config.py` with `pydantic-settings` Settings class (DB URL, Saihu keys, JWT secret, timezone, task poll interval, etc.)
- [X] T013 Create `backend/app/core/logging.py` configuring `structlog` JSON output + context binding
- [X] T014 Create `backend/app/core/exceptions.py` defining `SaihuAPIError`, `SaihuRateLimited`, `SaihuAuthExpired`, `SaihuBizError`, `BusinessError`, `NotFound`
- [X] T015 Create `backend/app/core/timezone.py` with `to_beijing(raw_str, marketplace_id)` helper and `MARKETPLACE_TO_TIMEZONE` mapping
- [X] T016 Create `backend/app/db/base.py` with SQLAlchemy 2.0 `DeclarativeBase` and naming convention
- [X] T017 Create `backend/app/db/session.py` with async engine + `async_sessionmaker` + `get_db()` dependency
- [X] T018 Initialize Alembic in `backend/alembic/` with async template; configure `backend/alembic.ini` to read DB URL from env

### Database models (all 20 tables)

- [X] T019 [P] Create `backend/app/models/global_config.py` with `GlobalConfig` ORM matching data-model.md §1.1
- [X] T020 [P] Create `backend/app/models/access_token.py` with `AccessTokenCache` matching §1.2
- [X] T021 [P] Create `backend/app/models/warehouse.py` with `Warehouse` matching §2.1 (fields + indexes)
- [X] T022 [P] Create `backend/app/models/shop.py` with `Shop` matching §2.2
- [X] T023 [P] Create `backend/app/models/sku.py` with `SkuConfig` matching §2.3
- [X] T024 [P] Create `backend/app/models/product_listing.py` with `ProductListing` matching §2.4 (unique + lookup indexes)
- [X] T025 [P] Create `backend/app/models/inventory.py` with `InventorySnapshotLatest` and `InventorySnapshotHistory` matching §3
- [X] T026 [P] Create `backend/app/models/in_transit.py` with `InTransitRecord` and `InTransitItem` matching §4
- [X] T027 [P] Create `backend/app/models/order.py` with `OrderHeader`, `OrderItem`, `OrderDetail`, `OrderDetailFetchLog` matching §5
- [X] T028 [P] Create `backend/app/models/zipcode_rule.py` with `ZipcodeRule` matching §6.1
- [X] T029 [P] Create `backend/app/models/suggestion.py` with `Suggestion`, `SuggestionItem` matching §6.2–6.3
- [X] T030 [P] Create `backend/app/models/overstock.py` with `OverstockSkuMark` matching §6.4
- [X] T031 [P] Create `backend/app/models/task_run.py` with `TaskRun` matching §7.1 (including partial unique index declaration)
- [X] T032 [P] Create `backend/app/models/sync_state.py` with `SyncState` matching §7.2
- [X] T033 [P] Create `backend/app/models/api_call_log.py` with `ApiCallLog` matching §8.1
- [X] T034 Aggregate imports in `backend/app/models/__init__.py` for Alembic autogenerate
- [X] T035 Generate initial Alembic migration `backend/alembic/versions/0001_initial.py` containing all 20 tables + indexes + partial unique index on `task_run.dedupe_key WHERE status IN ('pending','running')` + seed `global_config` and `sync_state` rows per data-model.md §10（hand-crafted SQL; global_config 种子延迟到首次启动时由应用插入以便计算 bcrypt hash）

### Authentication

- [X] T036 Create `backend/app/core/security.py` with bcrypt helpers (`hash_password`, `verify_password`) and JWT helpers (`create_access_token`, `decode_token`)
- [X] T037 Create `backend/app/api/auth.py` routes: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`。登录锁定语义：
  - 登录前检查 `global_config.login_locked_until > now()` → 返回 423 + `locked_until`
  - 密码错误 → `login_failed_count += 1`；若达到 5 → 设置 `login_locked_until = now() + 10min` 并 `login_failed_count = 0`
  - 密码正确且未锁定 → `login_failed_count = 0`、`login_locked_until = NULL`、签发 JWT
  - 所有计数修改走单条 `UPDATE ... WHERE id=1` SQL 避免并发竞态
- [X] T038 Create `backend/app/api/deps.py` with `get_current_session` dependency extracting + validating JWT from Authorization header

### Saihu API client

- [X] T039 Create `backend/app/saihu/sign.py` implementing HmacSHA256 signature per research.md R3 and `docs/saihu_api/开发指南/生产sign.md`
- [X] T040 Create `backend/app/saihu/rate_limit.py` with per-endpoint `AsyncLimiter(1, 1)` lazy cache
- [X] T041 Create `backend/app/saihu/marketplace.py` with full `MARKETPLACE_TO_COUNTRY` + `COUNTRY_TO_TIMEZONE` tables (21 sites from 站点对应关系.md)（实际数据在 `app/core/timezone.py`，本模块 re-export）
- [X] T042 Create `backend/app/saihu/client.py` with `SaihuClient` (async httpx client, auto-sign, per-endpoint rate limit, tenacity retry with 40001 token-refresh + 40019 backoff, writes every call to `api_call_log`)
- [X] T043 [P] Create `backend/app/saihu/token.py` for token acquisition via GET `/api/oauth/v2/token.json` + cache via `AccessTokenCache` table + proactive refresh 5min before expiry
- [X] T044 [P] Create `backend/app/saihu/endpoints/shop.py` wrapping `/api/shop/pageList.json`
- [X] T045 [P] Create `backend/app/saihu/endpoints/product_listing.py` wrapping `/api/order/api/product/pageList.json` with `match=true` + `onlineStatus=active` filtering + pagination iterator
- [X] T046 [P] Create `backend/app/saihu/endpoints/warehouse.py` wrapping `/api/warehouseManage/warehouseList.json` with pagination
- [X] T047 [P] Create `backend/app/saihu/endpoints/inventory.py` wrapping `/api/warehouseManage/warehouseItemList.json` with pagination
- [X] T048 [P] Create `backend/app/saihu/endpoints/out_records.py` wrapping `/api/warehouseInOut/outRecords.json` with `searchField=remark, searchValue=在途中` filter
- [X] T049 [P] Create `backend/app/saihu/endpoints/order_list.py` wrapping `/api/order/pageList.json` with `dateType=updateDateTime` support
- [X] T050 [P] Create `backend/app/saihu/endpoints/order_detail.py` wrapping `/api/order/detailByOrderId.json`
- [X] T051 [P] Create `backend/app/saihu/endpoints/purchase_create.py` wrapping `/api/purchase/create.json` (num as string, includeTax "0"/"1")
- [X] T052 Add Saihu client unit tests in `backend/tests/unit/test_sign.py` covering sign generation fixture from `docs/saihu_api/开发指南/生产sign.md`

### Task system (Scheduler + Queue + Worker)

- [ ] T053 Create `backend/app/tasks/queue.py` with `enqueue(job_name, dedupe_key=None, trigger_source, payload)` using transactional INSERT + catching `UniqueViolationError` → return existing task id per FR-058b/c
- [ ] T054 Create `backend/app/tasks/worker.py` with single-worker asyncio loop: atomic claim via `UPDATE ... FOR UPDATE SKIP LOCKED RETURNING *` + heartbeat loop (30s) + 2min lease
- [ ] T055 Create `backend/app/tasks/reaper.py` running every 60s: `UPDATE task_run SET status='failed', error_msg='Lease expired' WHERE status='running' AND lease_expires_at < now()`
- [ ] T056 Create `backend/app/tasks/scheduler.py` with APScheduler `AsyncIOScheduler` configured：
  - 全局 `job_defaults={'max_instances': 1, 'coalesce': True, 'misfire_grace_time': 60}` 防止同一调度触发器叠加
  - 按 `global_config.sync_interval_minutes` 设置每小时同步触发器（入队 product_listing / inventory / out_records / order_list / order_detail）
  - `warehouse` 单独设置为每日一次
  - 按 `calc_cron`（默认 08:00 Asia/Shanghai）设置规则引擎触发器
  - 每日 02:00 设置库存归档触发器
  - **每次触发只调用 `enqueue(...)`，业务执行在 Worker 侧**
- [ ] T057 Create `backend/app/tasks/jobs/__init__.py` as job registry mapping `job_name → async function`
- [ ] T058 Create `backend/app/api/task.py` routes per `contracts/task.yaml`: list, POST enqueue, GET `{id}`, POST `{id}/cancel`
- [ ] T059 Add worker/scheduler/reaper lifecycle to `backend/app/main.py` lifespan (start on startup, graceful shutdown)

### Frontend shell

- [ ] T060 [P] Create `frontend/src/main.ts` with Vue + Pinia + Router + Element Plus + global styles
- [ ] T061 [P] Create `frontend/src/styles/tokens.scss` with Ryvix design tokens (colors, radii, shadows, spacing) per spec Frontend Design Direction
- [ ] T062 [P] Create `frontend/src/styles/element-overrides.scss` customizing Element Plus components to match tokens
- [ ] T063 [P] Create `frontend/src/router/index.ts` with all 12 routes + auth guard
- [ ] T064 [P] Create `frontend/src/stores/auth.ts` (Pinia) managing token + login state
- [ ] T065 [P] Create `frontend/src/api/client.ts` axios wrapper with bearer injection + 401 redirect
- [ ] T066 [P] Create `frontend/src/api/auth.ts` + `frontend/src/views/LoginView.vue` implementing login page
- [ ] T067 [P] Create `frontend/src/components/AppLayout.vue` with left sidebar + top bar + content slot (per Ryvix layout)
- [ ] T068 [P] Create `frontend/src/components/TaskProgress.vue` reusable progress indicator polling `GET /api/tasks/{id}` every 2s
- [ ] T069 [P] Create `frontend/src/api/task.ts` + `frontend/src/stores/task.ts` for task polling management

**Checkpoint**: DB migrated, auth works, Saihu client testable, task system operational, frontend shell renders login + empty layout. All user stories can now begin in parallel.

---

## Phase 3: User Story 1 - 查看每日补货建议并审核推送 (P1) 🎯 MVP

**Goal**: 采购员看到每日自动生成的补货建议单，审核后一键推送至赛狐创建采购单。

**Independent Test**: 预置 SKU 配置 + 库存快照 + 订单 + 邮编规则 → 手动触发规则引擎 → 前端看到排序建议列表 → 勾选推送 → 赛狐侧出现采购单。

### Sync implementations (feed the engine)

- [ ] T070 [P] [US1] Create `backend/app/sync/product_listing.py` job: paginate listing endpoint → UPSERT `product_listing`, update `sync_state.sync_product_listing`
- [ ] T071 [P] [US1] Create `backend/app/sync/warehouse.py` job: full sync warehouse list → UPSERT `warehouse` (new records flagged "待指定国家")
- [ ] T072 [P] [US1] Create `backend/app/sync/inventory.py` job: paginate inventory endpoint → UPSERT `inventory_snapshot_latest` (null→0 handling); **仅写入 `available` + `reserved` 字段，跳过 `stockWait`（在途口径由 T073 "其他出库列表" 独立管理，见 FR-017/FR-017a~d）**
- [ ] T073 [US1] Create `backend/app/sync/out_records.py` job implementing FR-017a/b/c: `sync_start_time` snapshot → paginate with `searchField=remark, searchValue=在途中` → UPSERT `in_transit_record` + `in_transit_item` → post-sync aging `UPDATE in_transit_record SET is_in_transit=false WHERE last_seen_at < sync_start_time`
- [ ] T074 [US1] Create `backend/app/sync/order_list.py` job per FR-021: `dateType=updateDateTime` + `dateStart=sync_state.last_success_at-5min` + paginate → UPSERT `order_header` by `(shop_id, amazon_order_id)` + `order_item` by `(order_id, order_item_id)` with time conversion via `core/timezone.py`
- [ ] T075 [US1] Create `backend/app/sync/order_detail.py` job per FR-022/023: query orders whose `seller_sku IN (SELECT seller_sku FROM product_listing)` AND `(shop_id, amazon_order_id) NOT IN order_detail_fetch_log` → call detail endpoint one-by-one (rate-limited) → UPSERT `order_detail` + `order_detail_fetch_log`
- [ ] T076 [P] [US1] Create `backend/app/sync/shop.py` job for manual shop-list refresh (filters `status='0'`)
- [ ] T077 [US1] Wire all sync jobs into `backend/app/tasks/jobs/` registry with progress reporting (`current_step`, `step_detail`, `total_steps`)
- [ ] T078 [US1] Register sync job handlers in `backend/app/tasks/jobs/` registry so that the scheduler triggers defined in T056 resolve to real executors: every-hour group = {product_listing, inventory, out_records, order_list, order_detail} chained in order; daily group = {warehouse}

### Rule engine (Step 1–6)

- [ ] T079 [US1] Create `backend/app/engine/step1_velocity.py` implementing FR-028: query `order_item JOIN order_header` filtered by `order_status IN (Shipped, PartiallyShipped)`, `purchase_date IN [昨天-29, 昨天]`, `marketplace_to_country(mkt_id)`, compute `effective = max(shipped - refund, 0)`, bucket by date, apply `d7/7×0.5 + d14/14×0.3 + d30/30×0.2`
- [ ] T080 [US1] Create `backend/app/engine/step2_sale_days.py` implementing FR-030: aggregate `inventory_snapshot_latest(available+reserved)` by country + `in_transit_item JOIN in_transit_record WHERE is_in_transit=true` by country → `sale_days = stock/velocity`
- [ ] T081 [US1] Create `backend/app/engine/step3_country_qty.py` implementing FR-031: `raw = TARGET × velocity − stock`, `country_qty = max(raw, 0)`, collect negatives as `overstock_countries`
- [ ] T082 [US1] Create `backend/app/engine/step4_total.py` implementing FR-032: filter `country_qty > 0`, `total = Σcountry_qty + Σvelocity×BUFFER − (local_available + local_reserved)`, `total = max(total, 0)`, local warehouses via `warehouse.type = 1`
- [ ] T083 [US1] Create `backend/app/engine/zipcode_matcher.py` implementing FR-034/034a: `normalize_postal(code)` (strip + remove `-` and spaces) → iterate `zipcode_rule` ordered by priority → first hit wins → unknown otherwise
- [ ] T084 [US1] Create `backend/app/engine/step5_warehouse_split.py` implementing simplified FR-033: load SKU's country orders (via JOIN with order_detail), apply zipcode_matcher, compute real-distribution ratios, zero-data fallback = equal split across maintained country warehouses
- [ ] T085 [US1] Create `backend/app/engine/step6_timing.py` implementing FR-035: `T_ship = today + round(sale_days − TARGET)`, `T_purchase = T_ship − lead_time`, lead_time priority sku_config > global, set `urgent = any(T_purchase <= today)`
- [ ] T086 [US1] Create `backend/app/engine/runner.py` orchestrating Step 1–6 over all `sku_config.enabled=true`: pre-check push_blocker (FR-047) by looking up `commodity_id` in `product_listing`, insert `suggestion` header, bulk-insert `suggestion_item` rows, archive prior draft/partial `suggestion` records; emit progress step updates
- [ ] T087 [US1] Register `calc_engine` job in `backend/app/tasks/jobs/calc_engine.py` with scheduler trigger at `calc_cron` (default 08:00 Asia/Shanghai)
- [ ] T088 [P] [US1] Add unit tests in `backend/tests/unit/test_engine_step1.py` covering velocity date bucketing + effective formula with fixtures (incl. refund, canceled, partial shipped)
- [ ] T089 [P] [US1] Add unit tests in `backend/tests/unit/test_engine_step3.py` for negative-raw clamping + overstock collection
- [ ] T090 [P] [US1] Add unit tests in `backend/tests/unit/test_engine_step4.py` for total formula (with/without local warehouses, with/without overstock countries)
- [ ] T091 [P] [US1] Add unit tests in `backend/tests/unit/test_zipcode_matcher.py` covering number/string/all-operators/priority/normalize (`-`, spaces, EU + JP formats)
- [ ] T092 [P] [US1] Add unit tests in `backend/tests/unit/test_engine_step5.py` for real-distribution path + zero-data fallback path

### Suggestion API

- [ ] T093 [US1] Create `backend/app/schemas/suggestion.py` Pydantic DTOs per `contracts/suggestion.yaml` (Suggestion, SuggestionItem, Patch, PushRequest)
- [ ] T094 [US1] Create `backend/app/api/suggestion.py` routes: `GET /api/suggestions`, `GET /api/suggestions/current`, `GET /api/suggestions/{id}`, `PATCH /api/suggestions/{id}/items/{item_id}`, `POST /api/suggestions/{id}/push`, `POST /api/suggestions/{id}/archive`
- [ ] T095 [US1] In PATCH handler validate non-negative numbers per FR-043; persist without re-running engine
- [ ] T096 [US1] In POST push handler: validate `len(item_ids) ≤ 50` (FR-045a) + reject items with `push_blocker` set (FR-047) + enqueue `push_saihu` task with payload `{suggestion_id, item_ids}`

### Purchase pushback

- [ ] T097 [US1] Create `backend/app/pushback/purchase.py` job: load `suggestion_item` rows by ids, build purchase request `{warehouseId, action:"1", includeTax, items:[{commodityId, num:str(total_qty)}]}`, call saihu `purchase_create` endpoint, parse response list, update each `suggestion_item.push_status + saihu_po_number / push_error`, update parent `suggestion` aggregate counters + status transitions (draft→partial→pushed)
- [ ] T098 [US1] Implement auto-retry inside `pushback/purchase.py` up to 3 attempts per failed sub-item (FR-046) with tenacity
- [ ] T099 [US1] Register `push_saihu` in `backend/app/tasks/jobs/push_saihu.py` with progress updates

### Sync trigger & engine APIs

- [ ] T100 [US1] Create `backend/app/api/sync.py` routes per `contracts/sync.yaml` mapping to task enqueue (sync_all, sync_product_listing, sync_inventory, sync_out_records, sync_orders, sync_warehouse)
- [ ] T101 [US1] Add `POST /api/engine/run` route that archives existing draft/partial (with manual confirm handling via query param) + enqueues `calc_engine`

### Frontend — Suggestion list & detail

- [ ] T102 [P] [US1] Create `frontend/src/api/suggestion.ts` with typed client for all suggestion endpoints
- [ ] T103 [US1] Create `frontend/src/views/SuggestionListView.vue`: main list sorted by earliest `t_purchase` ascending, urgent rows red-highlighted, filter by SKU keyword / status / country, pagination
- [ ] T104 [US1] Create `frontend/src/views/SuggestionDetailView.vue`: expanded per-country/per-warehouse breakdown, editable fields (total/country/warehouse/time), non-negative validation, save button, overstock countries panel
- [ ] T105 [US1] Create `frontend/src/components/PushDialog.vue`: multi-select with 50-item limit warning, disable items carrying `push_blocker` with tooltip, confirm → call push endpoint → subscribe to returned task_id via `TaskProgress`
- [ ] T106 [US1] Create `frontend/src/components/SkuCard.vue` reusable card showing commodity_name + image (from `product_listing` join) + urgent badge
- [ ] T107 [US1] Create `frontend/src/views/ManualTaskView.vue`: buttons to trigger sync/engine; subscribe returned task_id via `TaskProgress`

**Checkpoint**: MVP ready. Rule engine runs end-to-end,採购员 can审核 + 推送。

---

## Phase 4: User Story 2 - 维护 SKU 配置与全局参数 (P2)

**Goal**: 采购员维护 SKU 级 lead_time / enabled + 全局参数。

**Independent Test**: 修改 SKU lead_time → 触发引擎 → 该 SKU 的 T_purchase 变化。

- [ ] T108 [US2] Create `backend/app/schemas/config.py` Pydantic DTOs per `contracts/config.yaml` (GlobalConfig, SkuConfig patches)
- [ ] T109 [US2] Create `backend/app/api/config.py` routes: `GET/PATCH /api/config/global`, `GET /api/config/sku`, `PATCH /api/config/sku/{commodity_sku}` with JOIN to `product_listing` for display fields
- [ ] T110 [US2] In global config PATCH validate `include_tax ∈ {"0","1"}` and `shop_sync_mode ∈ {all, specific}`
- [ ] T111 [P] [US2] Create `frontend/src/api/config.ts`
- [ ] T112 [P] [US2] Create `frontend/src/views/GlobalConfigView.vue`: form with all global params + save
- [ ] T113 [P] [US2] Create `frontend/src/views/SkuConfigView.vue`: searchable paginated table of enabled SKUs with inline edit for `enabled` and `lead_time_days`

**Checkpoint**: US1 + US2 work independently.

---

## Phase 5: User Story 3 - 维护仓库→国家映射与邮编规则 (P2)

**Goal**: 采购员维护仓库国家映射 + 邮编规则。

**Independent Test**: 新增邮编规则 → 运行引擎 → 该 SKU 的 warehouse_breakdown 按规则分配。

- [ ] T114 [US3] Extend `backend/app/api/config.py` with routes: `GET /api/config/warehouse`, `PATCH /api/config/warehouse/{id}/country`
- [ ] T115 [US3] Extend `backend/app/api/config.py` with zipcode-rule CRUD: `GET /api/config/zipcode-rules`, `POST`, `PATCH /{id}`, `DELETE /{id}`
- [ ] T116 [US3] Add validation in zipcode-rule PATCH/POST: `prefix_length 1–10`, `operator` enum, `value_type` enum, `warehouse_id` exists
- [ ] T117 [US3] Extend `backend/app/api/config.py` with shop routes: `GET /api/config/shops`, `POST /api/config/shops/refresh` (enqueues `sync_shop` task), `PATCH /api/config/shops/{id}` (sync_enabled toggle)
- [ ] T118 [P] [US3] Create `frontend/src/views/WarehouseView.vue`: table of warehouses with inline country edit, "待指定国家" badge, replenish_site_raw shown as hint
- [ ] T119 [P] [US3] Create `frontend/src/views/ZipcodeRuleView.vue`: rule CRUD with priority drag-sort + operator dropdown + number/string type switch
- [ ] T120 [P] [US3] Create `frontend/src/views/ShopView.vue`: list + manual refresh button (calling refresh endpoint → subscribe task) + sync_enabled toggle + disable rows with `status!='0'`

**Checkpoint**: US1 + US2 + US3 work.

---

## Phase 6: User Story 4 - 查询历史补货建议 (P3)

**Goal**: 采购员按日期/状态/SKU 查询历史建议。

**Independent Test**: 跑几天计算 → 查询前一天建议单 → 看到明细 + 配置快照 + 推送结果。

- [ ] T121 [US4] Extend `backend/app/api/suggestion.py` `GET /api/suggestions` to support filters `date_from / date_to / status / sku` + pagination per contracts
- [ ] T122 [US4] Ensure historical detail endpoint returns `global_config_snapshot` read-only (already FR-036)
- [ ] T123 [P] [US4] Create `frontend/src/views/HistoryView.vue`: date range + status + SKU search → paginated list → click into read-only detail view reusing `SuggestionDetailView` in read-only mode

**Checkpoint**: US1 + US2 + US3 + US4 work.

---

## Phase 7: User Story 5 - 查看积压提示与赛狐接口监控 (P3)

**Goal**: 采购员查看积压 SKU + 赛狐接口监控。

**Independent Test**: 某 SKU 全局 velocity=0 + 库存>0 → 积压提示页显示 → 标为已处理后从默认视图隐藏；某接口调用失败 → 监控页显示错误原因 → 点击重试生成新任务。

- [ ] T124 [US5] Extend `backend/app/engine/runner.py` to populate `overstock_sku_mark` during Step 1 (FR-032): UPSERT rows for SKUs with all-zero velocity + any warehouse available > 0, keeping prior `processed_at` if exists
- [ ] T125 [US5] Create `backend/app/api/monitor.py` routes per `contracts/monitor.yaml`: `GET /api/monitor/api-calls` (aggregated last 24h per endpoint), `GET /api/monitor/api-calls/recent`, `POST /api/monitor/api-calls/{id}/retry` (enqueues corresponding sync job); 在聚合视图中**额外计算** "订单邮编合规度"：`COUNT(order_header WHERE purchase_date < now() - interval '50 days' AND (shop_id, amazon_order_id) NOT IN order_detail_fetch_log)`，大于 0 时在 UI 警示 (FR-004 合规)
- [ ] T126 [US5] Add routes: `GET /api/monitor/overstock` (with show_processed filter) + `PATCH /api/monitor/overstock/{id}/processed`
- [ ] T127 [US5] Implement `last_sale_date` lookup in overstock response by querying latest non-zero `order_item` for the SKU
- [ ] T128 [P] [US5] Create `frontend/src/api/monitor.ts`
- [ ] T129 [P] [US5] Create `frontend/src/views/OverstockView.vue`: table with "标为已处理" button + show_processed toggle
- [ ] T130 [P] [US5] Create `frontend/src/views/ApiMonitorView.vue`: per-endpoint cards (last call, 24h rate, last error) + recent failures table + retry button

**Checkpoint**: All five user stories fully functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T131 [P] Add daily archive job in `backend/app/tasks/jobs/daily_archive.py`: copy `inventory_snapshot_latest` → `inventory_snapshot_history` at 02:00; register in scheduler
- [ ] T132 [P] Add DB backup cron script in `deploy/scripts/pg_backup.sh`: `pg_dump` + upload to OSS/COS using credentials from `.env`
- [ ] T133 [P] Add `backend/app/api/health.py` with `GET /healthz` reading DB connectivity
- [ ] T134 [P] Add structured request logging middleware in `backend/app/main.py` binding request id to structlog context
- [ ] T135 [P] Add Prometheus-style metrics endpoint `GET /metrics` exposing task counts per status (optional, for future observability)
- [ ] T136 [P] Run mypy strict on `backend/app/` and fix all type errors
- [ ] T137 [P] Run ruff + black on `backend/app/` and `backend/tests/` with `--check` in CI
- [ ] T138 [P] Run `vue-tsc --noEmit` on frontend and fix all type errors
- [ ] T139 [P] Run `eslint --max-warnings=0` on frontend
- [ ] T140 [P] Lighthouse/devtools measurement of SuggestionListView: verify FCP<1.5s, LCP<2.5s, first-bundle JS gzip<250KB
- [ ] T141 [P] Load test rule engine with 500 SKU fixture: verify completion <5min per SC-004
- [ ] T142 Verify first-time order backfill path (~3000 orders) completes within 1 hour per SC-008
- [ ] T143 Run `quickstart.md` end-to-end on a fresh VPS: verify 30-day stability proxy by running all flows once
- [ ] T144 Remove dead code, unused imports, TODO markers before final commit
- [ ] T145 Verify Constitution Check still passes post-implementation (update `specs/001-saihu-replenishment/checklists/requirements.md` if needed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately, no deps
- **Foundational (Phase 2)**: Depends on Setup; BLOCKS all user stories
- **User Story 1 (Phase 3, P1)**: Depends on Foundational only; can ship as MVP
- **User Story 2 (Phase 4, P2)**: Depends on Foundational; orthogonal to US1
- **User Story 3 (Phase 5, P2)**: Depends on Foundational; **US3 的初始化（仓库国家映射 + 至少一条 zipcode_rule）是 US1 能生成正确建议单的前置条件**。实际顺序：完成 Foundational → 完成 US3 的初始化（仅手工配置页即可，无需完整页面）→ 进入 US1 引擎开发。US3 的完整 UI 可与 US1 并行实现，但引擎运行前仓库国家与邮编规则必须落库
- **User Story 4 (Phase 6, P3)**: Depends on US1 (needs suggestion table populated); otherwise independent
- **User Story 5 (Phase 7, P3)**: Depends on Foundational + US1 (overstock table populated by engine); API monitor depends only on Foundational
- **Polish (Phase 8)**: After desired user stories complete

### Within Each Story

- Sync tasks → Engine → API → Frontend
- Models exist in Foundational phase already, so story tasks focus on business logic + API + UI

### Parallel Opportunities

- **Setup phase**: T002–T011 all parallel after T001
- **Foundational phase**:
  - Models T019–T033 parallel (different files)
  - Saihu endpoint wrappers T044–T051 parallel
  - Frontend shell T060–T069 parallel with backend foundational
- **US1**: Sync modules T070–T076 parallel; engine step tests T088–T092 parallel; frontend views parallel to backend API after API types shipped
- **US2, US3, US4, US5**: All parallel with each other after Foundational

---

## Parallel Execution Examples

### Setup kickoff
```text
After T001, dispatch in parallel:
  T002 T003 T004 T005 T006 T007 T008 T009 T010 T011
```

### Foundational models
```text
After T017, T018, dispatch in parallel:
  T019 T020 T021 T022 T023 T024 T025 T026 T027
  T028 T029 T030 T031 T032 T033
Then T034 aggregates, T035 generates migration
```

### US1 sync implementations
```text
After T069, dispatch in parallel:
  T070 T071 T072 T076
  (T073, T074, T075 sequential due to engine deps)
```

### US1 unit tests
```text
After T086, dispatch in parallel:
  T088 T089 T090 T091 T092
```

---

## Implementation Strategy

### MVP First (User Story 1 only)
1. Phase 1 Setup (T001–T011)
2. Phase 2 Foundational (T012–T069)
3. Phase 3 US1 (T070–T107)
4. **STOP**: Validate end-to-end on staging / demo
5. Ship

### Incremental Delivery After MVP
- Iteration 2: US2 (T108–T113) → shipable (config management added)
- Iteration 3: US3 (T114–T120) → shipable (warehouse/zipcode UI)
- Iteration 4: US4 (T121–T123) → shipable (history view)
- Iteration 5: US5 (T124–T130) → shipable (overstock + monitor)
- Iteration 6: Polish (T131–T145) → production hardening

### Parallel Team Strategy (if multiple devs later)
- Dev A: US1 backend (T070–T101)
- Dev B: US1 frontend (T102–T107)
- Dev C: US2/US3 (T108–T120) as soon as Foundational done
- Dev D: Polish & tooling (T131–T145)

---

## Notes

- Tests are narrowly scoped: rule engine math + saihu sign + zipcode matcher (the highest-risk correctness paths). Other paths can ship without tests per "tests optional" convention, but type checkers + lint MUST be green before merge
- Each user story phase ends with a checkpoint — validate before moving on
- The task_run architecture from Foundational makes every long-running operation visible and retryable, reducing the need for bespoke UX
- Commits should follow Conventional Commits and reference the task id (e.g. `feat(engine): T079 implement step 1 velocity`)
