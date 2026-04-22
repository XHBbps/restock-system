# Agent C — 功能完整度 + 测试缺口 + 文档漂移审计

> Stage 1 / Agent C（主会话手动执行，因 agent 1 次 API 断连失败 — 53 分钟后 socket error）
> 问题总数：13 条 / Critical: 2 / Important: 8 / Minor: 3

---

## Q1 — 功能缺失（代码 vs 文档对照）

### 问题 #1 — `specs/001-saihu-replenishment/spec.md` 整份 stale，描述的是"推送赛狐"旧架构

- 严重度：Important
- 位置：`specs/001-saihu-replenishment/spec.md`（整份）
- 现状：文件 metadata `Status: Draft (modules 1–8 + API reconciliation 确认完成)` + `Last Updated: 2026-04-08`。但 `PROGRESS.md §3.49`（2026-04-19）明确 Plan A 已把"推送赛狐" → "Excel 导出 + Snapshot 版本化"，spec.md 仍写 "勾选条目一键推送至赛狐生成采购单"（User Story 1）、"状态变为'已推送'并展示赛狐采购单号"（Acceptance Scenario 2）等。User Story 1/2/3 全部基于推送语义。
- 建议：标 `Status: Superseded by Plan A (2026-04-19)`，指向 `PROGRESS.md §3.49` 和 `docs/Project_Architecture_Blueprint.md`；或整份重写 User Story 为 Excel 导出。保持 legacy 文件方便追溯也行，但必须挂显式 Superseded 牌子。
- 工作量：S（加标签）/ M（重写）

### 问题 #2 — `AGENTS.md` 第 1 节"核心业务流"仍写"推送采购单回赛狐"

- 严重度：Important
- 位置：`AGENTS.md:17`
- 现状：
  > 赛狐只读同步 → 补货建议计算（6 步引擎）→ 建议编辑 → **推送采购单回赛狐**
  
  CLAUDE.md 强调 AGENTS.md 优先级最高，新人读到这里会被误导。第 11 节约束里还有 "已生成的建议单 JSONB 快照字段不可变（如 country_breakdown **已推送后**）" 也是旧话术，应为"已导出后"。第 11 节另一条"赛狐数据只读同步，不回写到赛狐（**除推送采购单**）"也 stale。
- 建议：`AGENTS.md:17` 改"… 建议编辑 → Excel 导出 + 快照版本化回赛狐同步"；第 11 节三处"推送"措辞改"导出"。
- 工作量：S

### 问题 #3 — `docs/PROGRESS.md` 多处 `estock_item_count` typo + `calc_enabled` 残留

- 严重度：Minor
- 位置：`docs/PROGRESS.md:55,79,45,116`
- 现状：
  - Line 55（§2.3 引擎）："分别统计 procurement_item_count、**estock_item_count**" — 应为 `restock_item_count`（实际模型字段名）
  - Line 79（§2.5 前端）："嵌套路由 … 拆为 procurement / **estock** 子路由" — 应为 `restock`
  - Line 45（§2.2）："默认 08:00 `calc_engine`（可配置，`calc_enabled` 控制）" — `calc_enabled` 已删
  - Line 116（§3.52）："将 `calc_enabled` 纳入 scheduler reload 触发集合" — 同样已删
- 建议：`estock` 全局替换为 `restock`；删除 `calc_enabled` 两处引用，替换为 `suggestion_generation_enabled` 或直接省略。
- 工作量：S

### 问题 #4 — PROGRESS.md §2.3 "6 步流水线" 描述的 step4 公式过期

- 严重度：Minor
- 位置：`docs/PROGRESS.md:61`
- 现状：
  > `step4_total` — 总采购量（扣减国内库存 + 缓冲天数）
  
  但 PROGRESS.md §3.53 里已写出完整新公式（`Σcountry_qty + Σvelocity × buffer_days − (local.available + local.reserved) + Σvelocity × safety_stock_days`），§2.3 的 1 行描述没跟上 Plan B 的 safety_stock_days。
- 建议：§2.3 step4 改为 "总采购量（扣减本地库存 + 缓冲天数 + 安全库存天数）"，或直接 inline 公式。
- 工作量：S

---

## Q2 — 测试覆盖缺口

### 问题 #5 — CI 从未真正运行 integration tests（集成测试实际上被 skip）

- 严重度：**Critical**
- 位置：`.github/workflows/ci.yml:31-32`
- 现状：
  - CI backend job 运行 `python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider`
  - **没有** `services: postgres`（检查：`grep TEST_DATABASE_URL|postgres:|services:|replenish_test` 返回 0 match）
  - **没有** `TEST_DATABASE_URL` env var
  - `backend/tests/conftest.py:18-24` 的 `pytest_collection_modifyitems` 明确：没 `TEST_DATABASE_URL` → integration tests 全部标 `pytest.mark.skip`
  - 意味着：`test_engine_e2e.py` / `test_export_e2e.py` / `test_snapshot_api.py` / `test_suggestion_delete_with_snapshot.py` / `test_config_api.py` / `test_generation_toggle_api.py` / `test_health.py` 共 **28 条集成测试** 在 CI 中**从未运行**
  - Session-context 提示 #7 的真实答案就是此条。
- 建议：
  1. `ci.yml` 加 postgres service container：
     ```yaml
     services:
       postgres:
         image: postgres:16
         env:
           POSTGRES_PASSWORD: postgres
           POSTGRES_DB: replenish_test
         ports: ["5432:5432"]
         options: >-
           --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
     ```
  2. backend job `env:` 加 `TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/replenish_test`
  3. 可选：拆两个 job（unit 不依赖 DB / integration 依赖 postgres service），保持 pipeline 并行度。
- 工作量：M

### 问题 #6 — mypy 配置对 15 个模块 blanket 抑制真实类型错误

- 严重度：**Critical**
- 位置：`backend/pyproject.toml:140-169`
- 现状：`[[tool.mypy.overrides]]` 对 `app.api.{data,config,suggestion,monitor,task,auth}` / `app.sync.{inventory,out_records,order_list,order_detail,warehouse,shop}` / `app.tasks.{jobs.daily_archive,queue,scheduler}` / `app.saihu.{token,client}` 禁用 `dict-item` / `attr-defined` / `arg-type` / `no-any-return` / `no-untyped-def` / `no-untyped-call` / `index` / `union-attr` 全套。这解释了为什么 CI 的 `python -m mypy app` step 能通过（项目 `strict=true` 却有 51 error 的矛盾）。这也直接掩盖了 Agent A 的 Critical/Important 发现：
  - `api/suggestion.py:46-50` 5 条 dict_item 错误（真排序字典类型不统一）
  - `api/monitor.py:116-117` 2 条 index 错误（Row 当 ApiCallLog 用）
  - 若这些 override 持续存在，未来同类问题会持续潜入。
- 建议：逐模块消灭 override —
  1. 短期：保留但加 FIXME 注释 + 开 backlog ticket 列出每个 override 模块的具体类型问题
  2. 中期：每个模块单独整改（参考 Agent A 问题 #6 #7 #8 的精准 `cast` / `# type: ignore[attr-defined]` 方案），整改完成后从 overrides 列表删除
  3. 长期目标：`[[tool.mypy.overrides]]` 只剩第三方库（apscheduler / asyncpg / aiolimiter），应用代码全量 strict
- 工作量：L（跨模块累计 1-2 周）

### 问题 #7 — CI 前端未跑 ESLint（eslint 错误合并进主干）

- 严重度：Important
- 位置：`.github/workflows/ci.yml:40-59`（frontend job）
- 现状：frontend job 只有 `npm run build` / `npm run test:coverage` / `npm audit`。**没有** `npm run lint` 步骤（`grep npm run lint` → No matches）。Stage 0 发现的 `DataInventoryView.test.ts:61` 2 个 `no-useless-escape` 就是通过这个缺口合并进来的。
- 建议：ci.yml frontend job 加 `- name: Run frontend lint\n  run: npm run lint`，放在 build 之前（lint 快，先炸先收益）。
- 工作量：S

### 问题 #8 — `app/sync/inventory.py` 的 EU 映射没有对应的 `test_sync_inventory_eu.py`

- 严重度：Important
- 位置：`backend/tests/unit/`（缺 `test_sync_inventory_eu.py`）+ `backend/tests/unit/test_sync_inventory.py`（Grep `apply_eu_mapping` → 0 match）
- 现状：4 个 sync 入口中 3 个有专项 EU 单测（`test_sync_order_list_eu.py` / `test_sync_out_records_eu.py` / `test_sync_product_listing_eu.py`），**inventory 的 EU 映射没有专项测试**。`test_sync_inventory.py` 也不测 `apply_eu_mapping` 路径。如果 `app/sync/inventory.py:85` 的 EU 映射行为将来破了（如误把 `None` 不处理），不会被捕获。
- 建议：补 `backend/tests/unit/test_sync_inventory_eu.py`，参考 3 个 sibling 文件的结构（映射国家/非映射国家/空字符串/大小写/eu_countries 为空集合的兜底）。
- 工作量：S

### 问题 #9 — `app/tasks/reaper.py` 和 `app/tasks/jobs/daily_archive.py` 覆盖率低且无专项 test

- 严重度：Important
- 位置：`backend/tests/unit/`（缺 `test_reaper.py`、`test_daily_archive_job.py`）
- 现状：Stage 0 coverage：`app/tasks/reaper.py` 33%、`app/tasks/jobs/daily_archive.py` 42%。Reaper 负责僵尸任务回收，daily_archive 负责订单历史归档 — 两者都是生产关键后台逻辑，故障会引发数据不一致但无外部告警。项目有 `test_worker.py`、`test_dashboard_snapshot_job.py`、`test_scheduler_api.py`，但 reaper 和 daily_archive 没对应 test。
- 建议：
  - `test_reaper.py`：覆盖租约过期 → 任务 requeue、并发 reaper 不重复 reclaim（模拟两个 reaper 竞争同一个 orphan task）
  - `test_daily_archive_job.py`：覆盖归档阈值边界、空数据集、归档失败回滚
- 工作量：M

### 问题 #10 — `app/saihu/client.py` 覆盖率 0%，但 unit 目录里有 `test_saihu_client.py`

- 严重度：Minor
- 位置：`backend/app/saihu/client.py`（291 lines, 0% coverage）+ `backend/tests/unit/test_saihu_client.py`
- 现状：Stage 0 inventory 列 saihu 全 0% coverage，但实际 unit 目录有 `test_saihu_client.py` / `test_saihu_rate_limit.py` / `test_saihu_sync_helpers.py` / `test_saihu_token.py` / `test_sign.py`。说明这些测试大概率 mock 了 HTTP 层后没触及 `client.py` 的真实代码路径，或只测了 helpers 不走主流程。评估：第三方 API wrapper 深度 mock 后不覆盖 client 主体是常见做法，不一定是 bug；但 0% 与 test 存在的事实不匹配，值得快速确认测试是否真的在测 client。
- 建议：运行 `pytest tests/unit/test_saihu_client.py --cov=app.saihu --cov-report=term-missing`，如果仍 0% 说明测试只走 mock 路径。判断：
  - 如果测试意图是"测 helpers / retry / rate-limit"，接受 client.py 0%
  - 如果意图是"测 client main flow"，补 fixture 让请求实际穿过 client wrapper
- 工作量：S（查证）

### 问题 #11 — `app/api/suggestion.py::patch_item` 的 urgent 重算边界

- 严重度：Minor
- 位置：`backend/app/api/suggestion.py:251-257` vs `backend/tests/unit/test_suggestion_patch.py`
- 现状：`patch_item` 在 `country_breakdown` 变更时调用 `has_urgent_sale_days(..., countries=positive_qty_countries(effective_country_breakdown))` 重算 `urgent`。`test_suggestion_patch.py` 有 `test_suggestion_patch_recomputes_urgent_from_sale_days_and_lead_time`、`test_suggestion_patch_ignores_missing_sale_days_when_recomputing_urgent` 两条 — 覆盖主路径。但没测：
  - `effective_country_breakdown` 全 0（空集合 countries） → `has_urgent_sale_days` 返回 False 的行为
  - SKU level `lead_time_days` 来自 `SkuConfig` vs `global_config_snapshot` fallback 的优先级 — 是否覆盖 `SkuConfig.lead_time_days=None` → snapshot 兜底 → default 50 三条路径
- 建议：补两条边界 test case 到 `test_suggestion_patch.py`。
- 工作量：S

---

## Q3 — 文档漂移

### 问题 #12 — `docs/Project_Architecture_Blueprint.md` 与当前代码可能有漂移

- 严重度：Important
- 位置：`docs/Project_Architecture_Blueprint.md`（未直接读，但按 AGENTS.md §9.1 映射表是"架构真理源"）
- 现状：Agent C 为效率限制没逐行比对 Blueprint 和代码；但 spec.md 和 AGENTS.md 都有"推送"残留，Blueprint 高概率有同类问题（推送 API、推送字段、推送状态机描述）。PROGRESS.md §3.49 改动之大（删除 `commodity_id.py` / `pushback/` / `purchase_create.py` 整块模块）需要 Blueprint 主动跟进。
- 建议：
  1. Blueprint 按 AGENTS.md §9.1 映射表逐条对照当前代码复核（特别是"赛狐集成层" / "规则引擎数据流" / "建议单状态机" 三节）
  2. 任何已删除模块 / 已改名字段必须更新
  3. 复核完成后加 `## 变更记录` 段落标明本次对齐日期
- 工作量：M

### 问题 #13 — `docs/PROGRESS.md` "最近更新" 日期 vs 实际最新变化

- 严重度：Minor
- 位置：`docs/PROGRESS.md:3`
- 现状：`最近更新：2026-04-21`。今天是 2026-04-22，且本次 Stage 0 修复刚改了 `backend/Dockerfile`（commit `58bee85`）和 `docs/superpowers/reviews/2026-04-21-inventory.md`。这不算漂移 — PROGRESS.md 记录的是"业务能力最近更新"而非"仓库最近 commit"。但 AGENTS.md §9.2 关闭清单第 5 条："`docs/PROGRESS.md` 的'最近更新'日期是否同步为本次任务日期？" — 如果 Stage 0 的环境卡点修复被视作本轮任务一部分，严格意义上应该改成 `2026-04-22（Stage 0 review + Dockerfile 修复）`。判断这是执行偏好不是 bug。
- 建议：若 Stage 3 修复批量出货时，把 PROGRESS.md 最近更新日期和"本次整改小节"一起加上。无需单独动作。
- 工作量：—
