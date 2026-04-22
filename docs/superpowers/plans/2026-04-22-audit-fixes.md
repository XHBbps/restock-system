# 2026-04-22 全量 Audit 修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/superpowers/reviews/2026-04-21-full-audit.md` 的 P0 / P1 / P2 三层 63 条问题全量修复。分成 7 个主题打包并行推进，每包独立 branch + PR。

**Architecture:**
- **分包原则**：按"主题 + 文件耦合度"分包，一个包内文件修改范围高度相关；跨文件系统的问题（如 mypy 类型债 + CI workflow）各自归其所属
- **提交粒度**：每包内部按 commit 级 task 拆分；同一文件小改动可合并到一个 commit
- **验证机制**：每包完成后跑一次"该域相关 test"（ruff / mypy / pytest unit+integration / vue-tsc / vite build），最后整合前跑完整 Stage 0 扫描命令确认无回归
- **执行顺序**：打包 #1 最先（P0 闪电修），打包 #2~#7 可并行（相互无依赖）；backlog P2 全部归入对应主题包内顺手修

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + Alembic + openpyxl；Vue 3 + TypeScript + Vite + Element Plus；pytest + ruff + mypy + vue-tsc + ESLint；Docker Compose + Caddy + GitHub Actions

**Pre-flight（执行前）：**
- 读 `docs/superpowers/reviews/2026-04-21-full-audit.md` 对照本 plan 的每条任务定位
- 读 `docs/superpowers/reviews/2026-04-21-inventory.md` 的 "Stage 1 agent 推荐 pytest 命令" 段获取测试入口
- 分支策略：建议 `feature/audit-fixes-p0` / `feature/audit-fixes-mypy-debt` / ... 每包独立
- 本地 dev 容器运行：`docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev up -d`
- 当前分支：`feature/split-procurement-restock-and-eu`（可直接在这支做，或 rebase 到 master 后再开新 topic 分支）

---

## 文件结构全景（修改 / 新增概览）

**后端修改：**
- `backend/app/engine/step4_total.py`
- `backend/app/config.py`
- `backend/app/api/suggestion.py`
- `backend/app/api/monitor.py`
- `backend/app/api/metrics.py`
- `backend/app/models/suggestion.py`（+ alembic migration）
- `backend/app/services/excel_export.py`（retention 钩子）
- `backend/app/tasks/jobs/daily_archive.py`
- `backend/app/tasks/queue.py` / `app/tasks/scheduler.py` / `app/tasks/worker.py`（mypy 精准 ignore）
- `backend/pyproject.toml`（mypy overrides 逐模块删除）
- `backend/tests/unit/test_sync_inventory_eu.py`（新）
- `backend/tests/unit/test_reaper.py`（新）
- `backend/tests/unit/test_daily_archive_job.py`（新）
- `backend/app/tasks/jobs/retention.py`（新）
- `backend/app/core/locks.py`（新）
- 若干零散测试补边界

**前端修改：**
- `frontend/src/views/history/SuggestionHistoryView.vue`（新，替代 Procurement/Restock 重复）或共用 composable
- `frontend/src/views/history/ProcurementHistoryView.vue` / `RestockHistoryView.vue`（瘦身）
- `frontend/src/components/SuggestionDetailDialog.vue`（响应式 + 关闭按钮）
- `frontend/src/views/data/DataInventoryView.vue`（placeholder 修 + 响应式）
- `frontend/src/views/data/*.vue`（filter toolbar 响应式）
- `frontend/src/views/suggestion/ProcurementListView.vue` / `RestockListView.vue`（empty 文案区分 + el-table fixed 列）
- `frontend/src/views/__tests__/DataInventoryView.test.ts`（eslint fix）
- `frontend/src/utils/allocation.ts` + `allocation.test.ts`（删除）
- `frontend/vite.config.ts`（chunk warning 放宽）
- `frontend/src/api/suggestion.ts` + 后端对应 schema（status_code）

**部署 / 运维修改：**
- `.gitignore`（`*.exe` / `*.lnk` / 根目录 `.mypy_cache/`）
- `.github/workflows/ci.yml`（postgres service + TEST_DATABASE_URL + npm run lint）
- `.github/workflows/deploy.yml`（environment approval）
- `deploy/Caddyfile`（HSTS preload + Cookie Secure）
- `deploy/scripts/validate_env.sh`（JWT_SECRET / LOGIN_PASSWORD / SAIHU_* 预检）
- `deploy/scripts/deploy.sh`（备份验证）
- `deploy/data/pg-local/`（删除或 gitignore）

**文档同步：**
- `AGENTS.md:17` + §11（推送→导出）
- `docs/PROGRESS.md`（estock typo / calc_enabled 残留 / step4 公式）
- `docs/Project_Architecture_Blueprint.md`（逐节对齐 Plan A）
- `specs/001-saihu-replenishment/spec.md`（Superseded 标签或重写）
- `docs/superpowers/plans/archived/`（已完成 plan 归档）
- `docs/reviews/`（合并到 `docs/superpowers/reviews/` 或删）

---

## 打包 #1 — P0 闪电修（最先执行，半天）

**目标**：把 5 条 Critical 里 4 条闭环；最后 1 条（mypy override）进打包 #2。
**分支**：`feature/audit-fixes-p0`
**预期 PR 数**：1

### Task 1.1 — engine step4 purchase_qty clamp（P0-1 / Agent A #1）

- [ ] 改 `backend/app/engine/step4_total.py:66` `return int(purchase_qty)` → `return max(0, int(purchase_qty))`
- [ ] 新增 alembic migration `backend/alembic/versions/YYYYMMDD_HHMM_suggestion_item_purchase_qty_ge_zero.py`：
  - `op.execute("UPDATE suggestion_item SET purchase_qty = 0 WHERE purchase_qty < 0")`
  - `op.create_check_constraint("purchase_qty_non_negative", "suggestion_item", "purchase_qty >= 0")`
- [ ] 改 `backend/app/models/suggestion.py:77-102` `SuggestionItem.__table_args__` 加 `CheckConstraint("purchase_qty >= 0", name="purchase_qty_non_negative")`
- [ ] 补 `backend/tests/unit/test_engine_step4.py` 边界 case：本地库存 > 需求时 `compute_total` 返回 0（非负）
- [ ] 验证：`pytest tests/unit/test_engine_step4.py -v` 通过；跑 `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` 幂等
- [ ] Commit: `fix(backend): engine step4 clamp purchase_qty >= 0 + DB CheckConstraint`

### Task 1.2 — docs_enabled production hardening（P0-2 / Agent A #2）

- [ ] 改 `backend/app/config.py:69-72`：
  ```python
  def docs_enabled(self) -> bool:
      if self.app_env == "production":
          return False
      if self.app_docs_enabled is not None:
          return self.app_docs_enabled
      return True
  ```
- [ ] 补 `backend/tests/unit/test_runtime_settings.py`：在 `test_docs_disabled_by_default_in_production` 里加 `monkeypatch.delenv("APP_DOCS_ENABLED", raising=False)` + 新增断言 "production 即使 env=true 也返回 False"
- [ ] 验证：`pytest tests/unit/test_runtime_settings.py -v` 通过
- [ ] Commit: `fix(backend): docs_enabled() production 强制忽略 env override`

### Task 1.3 — CI 加 postgres service 跑 integration tests（P0-3 / Agent C #5）

- [ ] 改 `.github/workflows/ci.yml:14-38` backend job：
  ```yaml
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_PASSWORD: postgres
        POSTGRES_DB: replenish_test
      ports: ["5432:5432"]
      options: >-
        --health-cmd pg_isready --health-interval 10s
        --health-timeout 5s --health-retries 5
  env:
    TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/replenish_test
  ```
- [ ] 验证：本地 act 或 PR 触发后 CI 里能看到 integration tests 实际跑（non-skip）
- [ ] Commit: `ci: 加 postgres service + TEST_DATABASE_URL 让 integration tests 真跑`

### Task 1.4 — .gitignore 补 *.exe / *.lnk / 根目录 .mypy_cache（P0-4 / Agent E #1 + E #2）

- [ ] 编辑根目录 `.gitignore`，补：
  ```
  # 本地开发工具 / 快捷方式
  *.exe
  *.lnk
  cloudflared*

  # 根目录 mypy cache（backend/.mypy_cache 已在子层 gitignore）
  /.mypy_cache/
  ```
- [ ] `git rm --cached --ignore-unmatch` 确认无已跟踪 exe/lnk（目前 grep 结果 0）
- [ ] `git status` 应无 cloudflared / Ai_project.lnk 出现
- [ ] Commit: `chore: .gitignore 补 *.exe / *.lnk / 根目录 .mypy_cache/`

### Task 1.5 — 打包 #1 整合验证

- [ ] 本地跑完整 Stage 0 命令（见 `docs/superpowers/reviews/2026-04-21-inventory.md` 的推荐命令）— 应 310+ passed / 0 failed
- [ ] 跑前端 `npx vue-tsc --noEmit && npx vite build` 无回归
- [ ] 打开 PR 指向 master

---

## 打包 #2 — mypy 类型债集中整改

**目标**：消灭 `pyproject.toml` 15 模块 blanket override，恢复 strict 类型检查，让隐藏的 A#6/#7 真 bug 浮出。
**分支**：`feature/audit-fixes-mypy-debt`
**前置**：打包 #1 合并（避免冲突）
**预期 PR 数**：1-2

### Task 2.1 — 修 api/suggestion.py:46-50 排序 dict 类型声明（P1-A2 / Agent A #6）

- [ ] 改 `backend/app/api/suggestion.py:45` `sort_map` 类型：
  ```python
  from typing import Any
  from sqlalchemy.sql.elements import ColumnElement
  sort_map: dict[str, tuple[ColumnElement[Any], ...]] = { ... }
  ```
- [ ] 无需改 value（InstrumentedAttribute 是 ColumnElement 子类，`[Any]` 接受所有）
- [ ] Commit: `refactor(backend): suggestion sort_map 类型改 ColumnElement[Any] 消 5 条 dict_item`

### Task 2.2 — 修 api/monitor.py Row 存 dict 类型（P1-A3 / Agent A #7）

- [ ] 改 `backend/app/api/monitor.py:87` `last_call_per_endpoint: dict[str, ApiCallLog] = {}` → `dict[str, tuple[str, int, str | None, datetime]] = {}`
- [ ] 改 `line 107` 去掉 `# type: ignore[assignment]`
- [ ] 改 `line 116-117` 的 `last[1]` `last[2]` 保留（Row 支持 tuple index 且现在类型已对）
- [ ] 验证：`docker exec restock-dev-backend mypy app` 针对这两个文件无 dict_item / attr-defined / index 报错
- [ ] Commit: `fix(backend): api/monitor.py 明确 Row tuple 类型 + 去 type: ignore`

### Task 2.3 — 精准 ignore SQLAlchemy 2.x + asyncpg 类型存根缺失（P1-A4 / Agent A #8）

- [ ] 每处加精准 `# type: ignore[attr-defined]`：
  - `backend/app/tasks/worker.py:195` `result.rowcount`
  - `backend/app/tasks/worker.py:232` `result.rowcount`
  - `backend/app/tasks/jobs/daily_archive.py:41` `result.rowcount`
  - `backend/app/tasks/jobs/daily_archive.py:54` `result.rowcount`
  - `backend/app/sync/order_list.py:158` `stmt.on_conflict_do_update(...)`
- [ ] 改 `backend/app/sync/order_detail.py:236` `marketplace_to_country(...)` 传入参数类型：上游强制转 `str | None`（或 `cast`）而非 `object`
- [ ] 改 `backend/app/sync/inventory.py:66` `dict(...)` 接收 `Sequence[Row]` → 用 `dict(r.tuple() for r in rows)` 或 `cast`
- [ ] 改 `backend/app/engine/step6_timing.py:111`：`compute_urgency_for_sku` 参数签名放宽为 `Mapping[str, float | int | None]`（与 `has_urgent_sale_days` 一致）
- [ ] `backend/app/tasks/scheduler.py:126` 的 `Any | None` isoformat 用 `assert` 或显式 `isinstance` 后调用
- [ ] Commit: `fix(backend): 精准 type: ignore 和参数类型收敛 SQLAlchemy 2.x + asyncpg 缺 stubs 处`

### Task 2.4 — 从 pyproject.toml 逐模块删 mypy override（P1-C3 / Agent C #6）

- [ ] 改 `backend/pyproject.toml:140-159` overrides 模块列表：**逐一**删除 `app.api.*` / `app.sync.*` / `app.tasks.*` / `app.saihu.*` 中已在 Task 2.1-2.3 清理过的模块
- [ ] 每删一个模块跑 `docker exec restock-dev-backend mypy app` 验证该文件不新增 error；如仍有 error 回滚该模块并补精准 ignore 再删
- [ ] 最终 overrides 列表只保留第三方模块（`apscheduler.*` / `aiolimiter.*` / `asyncpg.*`）
- [ ] Commit: `chore(backend): 删 pyproject.toml mypy blanket overrides 恢复 strict`

### Task 2.5 — 整合验证

- [ ] `docker exec restock-dev-backend mypy app` 全通过
- [ ] `pytest tests --cov=app` 不回归
- [ ] 打开 PR

---

## 打包 #3 — 历史页去重 + 状态 code 化

**目标**：消除 `ProcurementHistoryView.vue` 和 `RestockHistoryView.vue` 95% 重复；把 `statusTagType` 改基于后端 enum code 而非中文字面量。
**分支**：`feature/audit-fixes-history-dedup`
**预期 PR 数**：1

### Task 3.1 — 后端 Suggestion 列表响应加 display_status_code（P1-B2 前置）

- [ ] 改 `backend/app/api/suggestion.py:154-163` `_derive_display_status` 返回值结构：
  ```python
  class DisplayStatus(TypedDict):
      code: Literal["exported", "pending", "archived"]
      label: str
  ```
  或扩展 `SuggestionOut` 新增 `procurement_display_status_code` / `restock_display_status_code`
- [ ] `procurement_display_status` label 保留用于展示
- [ ] 改 `backend/app/schemas/suggestion.py` 对应 schema
- [ ] 补 test：`test_suggestion_list_api.py` 断言返回含 code
- [ ] Commit: `feat(backend): Suggestion 列表加 display_status_code 供前端 tag 色映射`

### Task 3.2 — 抽 SuggestionHistoryView 共用组件（P1-B1）

- [ ] 新建 `frontend/src/views/history/SuggestionHistoryView.vue`，接受 props `{ type: 'procurement' | 'restock' }`
- [ ] 内部根据 type 切换：
  - 列表前缀 `CG-` / `BH-`（用 `suggestionNoPrefix(type)`）
  - display_status_code / snapshot_count 字段名映射
  - 删除确认文案插值 "对应的 ${其他 type} 建议单"
- [ ] 把 `ProcurementHistoryView.vue` 和 `RestockHistoryView.vue` 改成薄 wrapper：
  ```vue
  <SuggestionHistoryView type="procurement" />
  ```
- [ ] 删除两份旧 view 的 `<script>` + `<style>` 重复代码
- [ ] 更新 router 配置（路径不变，component 映射到 wrapper）
- [ ] Commit: `refactor(frontend): 抽 SuggestionHistoryView 共用组件消除 95% 重复`

### Task 3.3 — 状态 tag 基于 code 映射（P1-B2）

- [ ] 改 `SuggestionHistoryView.vue:statusTagType(code: string)`：
  ```ts
  const STATUS_TAG_MAP = {
    exported: 'success',
    pending: 'warning',
    archived: 'info',
    error: 'danger',
  } as const
  function statusTagType(code: keyof typeof STATUS_TAG_MAP) { ... }
  ```
- [ ] 显示 label 仍用后端返回的中文
- [ ] 补 test：`frontend/src/views/history/__tests__/SuggestionHistoryView.test.ts`
- [ ] Commit: `refactor(frontend): 历史页状态 tag 改基于 code 非中文字面量`

### Task 3.4 — 验证

- [ ] `cd frontend && npx vue-tsc --noEmit && npx vite build`
- [ ] `npm run test -- --run`
- [ ] 人工在 dev 容器打开 /restock/history 两个 Tab 验证
- [ ] PR

---

## 打包 #4 — 数据保留三连 + Dashboard snapshot 自动失效

**目标**：为 task_run / inventory_snapshot_history / exports 三个增长型资源加 retention；给 dashboard snapshot 加失效机制。
**分支**：`feature/audit-fixes-retention`
**预期 PR 数**：1

### Task 4.1 — 新建 retention job（P1-D1 + P1-D2）

- [ ] 新建 `backend/app/tasks/jobs/retention.py`：
  ```python
  async def purge_task_run(ctx: JobContext, days: int = 90): ...
  async def purge_inventory_history(ctx: JobContext, days: int = 180): ...
  async def purge_exports(ctx: JobContext, days: int = 60): ...
  ```
- [ ] 每个函数用 `DELETE FROM ... WHERE created_at < now() - interval 'N days'` + 文件系统删除（exports）
- [ ] 注册到 `scheduler.py` cron：每天 04:00 跑一次
- [ ] 加 `global_config` 字段（或复用 env）配置保留天数
- [ ] 补 test：`backend/tests/unit/test_retention_job.py` 覆盖 3 个函数 + 边界（0 条 / 全部过期 / 部分过期）
- [ ] Commit: `feat(backend): 新增 retention job 清理 task_run / inventory_history / exports`

### Task 4.2 — exports 下载 API 处理 purged 文件（P1-D2 配套）

- [ ] 改 `backend/app/api/snapshot.py download` endpoint：文件不存在时返回 410 Gone + 提示 "已清理"
- [ ] 改 `excel_export_log` 迁移加 `file_purged_at: datetime | None`
- [ ] 前端详情页下载按钮 catch 410 显示 "该版本已过期清理"
- [ ] Commit: `feat(backend): 导出文件清理后返回 410 + 前端友好提示`

### Task 4.3 — Dashboard snapshot 自动失效（P1-D3）

- [ ] 改 `backend/app/models/dashboard_snapshot.py` 加 `stale: bool = False` 或 `expires_at: datetime | None` 字段 + alembic migration
- [ ] 改 `backend/app/api/config.py` 在 `update global_config`（eu_countries / restock_regions / target_days / lead_time_days 改动）后把 `dashboard_snapshot.stale = True`
- [ ] 改 `backend/app/api/metrics.py GET /dashboard`：若 `stale=True` 返回 `snapshot_status="refreshing"` + 自动 enqueue `refresh_dashboard_snapshot`（复用 dedupe）
- [ ] 补 test：integration `test_metrics_snapshot_api.py` 断言配置改动后自动失效
- [ ] Commit: `feat(backend): Dashboard snapshot 配置变更时自动 stale + 触发刷新`

### Task 4.4 — 验证

- [ ] `pytest tests --cov=app` 通过
- [ ] 手工 dev：改 `eu_countries` 后开 /workspace 确认 snapshot 被标 stale 并触发 refresh task
- [ ] PR

---

## 打包 #5 — 文档漂移收口

**目标**：把 Plan A（推送→导出）后残留的所有文档 stale 话术整改。
**分支**：`feature/audit-fixes-doc-drift`
**预期 PR 数**：1

### Task 5.1 — AGENTS.md 收口（P1-C2）

- [ ] 改 `AGENTS.md:17` "推送采购单回赛狐" → "Excel 导出 + 快照版本化"
- [ ] 改 `AGENTS.md` §11 三处 "推送" → "导出"
- [ ] Commit: `docs(agents): AGENTS.md 移除 Plan A 后 stale 推送话术`

### Task 5.2 — PROGRESS.md 修 typo + 过期字段（P2-C1 + P2-C2）

- [ ] 全局替换 `estock_item_count` → `restock_item_count`（仅 docs/ 下）
- [ ] 全局替换 `estock / procurement` → `restock / procurement`
- [ ] 删除 Line 45 / 116 对 `calc_enabled` 的引用，改为 `suggestion_generation_enabled` 或删
- [ ] §2.3 step4 公式行补 safety_stock_days："总采购量（扣减本地库存 + 缓冲天数 + 安全库存天数）"
- [ ] 更新 "最近更新" 日期为今天
- [ ] Commit: `docs(progress): 修 estock typo + calc_enabled 残留 + step4 公式更新`

### Task 5.3 — spec.md 加 Superseded 标签（P1-C1）

- [ ] 在 `specs/001-saihu-replenishment/spec.md` 顶部加：
  ```markdown
  > **⚠️ Superseded by Plan A (2026-04-19)**
  >
  > 本 spec 描述的"推送赛狐生成采购单"已在 Plan A 改为"Excel 导出 + Snapshot 版本化"。
  > 请参考 `docs/PROGRESS.md §3.49` 和 `docs/Project_Architecture_Blueprint.md` 的当前架构。
  > 本文件保留作历史追溯。
  ```
- [ ] 修改 metadata `Status: Superseded by Plan A (2026-04-19)`
- [ ] Commit: `docs(spec): 001-saihu-replenishment/spec.md 标 Superseded`

### Task 5.4 — Project_Architecture_Blueprint.md 对齐 Plan A（P1-C7）

- [ ] 通读 `docs/Project_Architecture_Blueprint.md` 全文，逐节对照当前代码
- [ ] 删除所有 "推送" / "推送采购单" / `pushback` / `push_saihu` 等残留
- [ ] 更新 "建议单状态机" 章（status 枚举 `draft / archived / error`）
- [ ] 更新 "规则引擎数据流" 章（安全库存 + EU 合并）
- [ ] 加 `## 变更记录` 章记录本次对齐日期
- [ ] Commit: `docs(arch): Project_Architecture_Blueprint.md 逐节对齐 Plan A 现状`

### Task 5.5 — 整合验证

- [ ] `grep -rn "推送\|pushback\|push_saihu\|calc_enabled\|estock" docs/ AGENTS.md specs/` 结果干净（除有意保留的历史章节）
- [ ] PR

---

## 打包 #6 — CI 安全网补全

**目标**：CI 跑 integration（P0-3 已在闪电修里做）+ eslint + deploy.yml 加强。
**分支**：`feature/audit-fixes-ci`
**前置**：打包 #1 合并（P0-3 已在其中）
**预期 PR 数**：1

### Task 6.1 — CI frontend 加 ESLint（P1-C4）

- [ ] 改 `.github/workflows/ci.yml` frontend job，在 `npm ci` 之后 `npm run build` 之前加：
  ```yaml
  - name: Run frontend lint
    run: npm run lint
  ```
- [ ] 验证：本地先修 `frontend/src/views/__tests__/DataInventoryView.test.ts:61` 的 2 条 `no-useless-escape`（归入本 task），再推 PR，CI lint 步骤 pass
- [ ] Commit: `ci: frontend job 加 npm run lint + 修 DataInventoryView.test.ts 2 条 no-useless-escape`

### Task 6.2 — deploy.yml 加 environment approval（P1-E4）

- [ ] 改 `.github/workflows/deploy.yml` 部署 job 添加：
  ```yaml
  environment:
    name: production
    url: https://<your-domain>
  ```
- [ ] 在 GitHub Settings → Environments 配置 "production" 需要 reviewer approval
- [ ] `workflow_dispatch` 保留（应急），但文档里说明需要 human approval
- [ ] Commit: `ci(deploy): production environment 加 reviewer approval 保护`

### Task 6.3 — 验证

- [ ] PR 触发 CI 看 lint step 真运行
- [ ] 手工测试 deploy workflow dispatch 触发后在 Actions 页面等待 approval

---

## 打包 #7 — 部署安全加固

**目标**：Caddyfile + validate_env.sh + deploy.sh 备份验证。
**分支**：`feature/audit-fixes-deploy-hardening`
**预期 PR 数**：1

### Task 7.1 — Caddyfile HSTS preload + Cookie Secure（P1-E3）

- [ ] 改 `deploy/Caddyfile` 生产配置：
  ```
  header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
  header Cache-Control "no-store" # 针对 API
  # 可选：Cookie 由后端设置 secure/httponly/samesite（FastAPI response.set_cookie）
  ```
- [ ] 同步改 `backend/app/main.py` 或 auth 流程的 cookie 设置，明确 `secure=True, httponly=True, samesite="strict"`
- [ ] 补 test 验证 /login 响应 cookie 属性
- [ ] Commit: `chore(deploy): Caddyfile HSTS preload + cookie Secure/HttpOnly/SameSite`

### Task 7.2 — validate_env.sh 生产 secret 预检（P1-E5）

- [ ] 改 `deploy/scripts/validate_env.sh` 加：
  ```bash
  if [ "$APP_ENV" = "production" ]; then
    [ "$JWT_SECRET" = "please_change_me_32_byte_minimum_key!" ] && fail "JWT_SECRET 未改"
    [ "$LOGIN_PASSWORD" = "please_change_me" ] && fail "LOGIN_PASSWORD 未改"
    [ -z "$SAIHU_CLIENT_ID" ] && fail "SAIHU_CLIENT_ID 必填"
    [ -z "$SAIHU_CLIENT_SECRET" ] && fail "SAIHU_CLIENT_SECRET 必填"
    [ ${#JWT_SECRET} -lt 32 ] && fail "JWT_SECRET 必须 >= 32 字节"
  fi
  ```
- [ ] 在 `deploy.sh:开头` 增加 `validate_env.sh` 硬阻断（失败则退出）
- [ ] Commit: `chore(deploy): validate_env.sh 补生产 secret 强校验`

### Task 7.3 — deploy.sh 备份验证 + 回滚文档（P2-E2）

- [ ] 改 `deploy/scripts/deploy.sh:57` pg_backup 后加：
  - `BACKUP_FILE=$(ls -t ${BACKUP_DIR}/*.sql.gz | head -1)`
  - `[ -s "$BACKUP_FILE" ] || fail "backup 文件为空"`
  - 可选 `gzip -t "$BACKUP_FILE"` 完整性检查
- [ ] 改 `deploy/scripts/rollback.sh` 补"数据库回滚需手动 restore_db.sh" 明确流程文档
- [ ] 更新 `docs/runbook.md` 加"回滚 SOP" 章节
- [ ] Commit: `chore(deploy): deploy.sh 加备份完整性验证 + 回滚 SOP 文档`

### Task 7.4 — 验证

- [ ] 本地跑 `bash deploy/scripts/validate_env.sh`（带 dev env）pass；带模拟 prod 空 env fail
- [ ] PR

---

## 打包 #BACKLOG — P2 杂项（顺手带上）

**目标**：剩余 25 条 P2 集中在一个 PR 里收尾，属于零碎细节不值单独 PR。
**分支**：`chore/audit-fixes-p2-misc`
**预期 PR 数**：1（可拆 2-3 个按主题）

### Task B.1 — 后端零碎（P2-A1 ~ P2-A4）

- [ ] 新建 `backend/app/core/locks.py` 集中 advisory lock key 常量（P2-A1）
- [ ] 改 `backend/app/api/monitor.py:85-105` raw `text()` → SQLAlchemy Core `select` + `over()`（P2-A2，可选，价值不大时跳过）
- [ ] `backend/app/api/suggestion.py patch_item updates` 改 TypedDict（P2-A3）
- [ ] 引擎数据结构三层 dict → dataclass / TypedDict（P2-A4，大改，可单独一个 commit）
- [ ] Commit: `refactor(backend): 后端 P2 杂项（locks 常量化 + updates TypedDict + engine dataclass）`

### Task B.2 — 前端零碎（P2-B1 ~ P2-B7）

- [ ] `ProcurementListView.table-toolbar__filters` wrapper 对齐 Restock（P2-B1）
- [ ] `PurchaseDateCell.vue:46` 注释改 "6 档" + session-context 同步（P2-B2）
- [ ] 历史页 delete 按钮硬编码色值 → scss token（P2-B3，新增 `$color-danger-dark`）
- [ ] 文案"至少6位" / "至少 6 位" 全局统一（P2-B4）
- [ ] `DataInventoryView.test.ts:61` 修 eslint no-useless-escape（**已在 Task 6.1 里做**，此处跳过）
- [ ] `SuggestionListView.totalSnapshotCount` 内联（P2-B6，可选保留）
- [ ] `RestockListView.editable` 无编辑 UI 加文档 hint（P2-B7）
- [ ] Commit: `refactor(frontend): 前端 P2 杂项（toolbar 对齐 + token 替换 + 文案统一）`

### Task B.3 — 测试补缺（P2-C3 + P2-C4 + Agent C #8 #9 整合）

- [ ] 新建 `backend/tests/unit/test_sync_inventory_eu.py`（P1-C5，参考其他 3 个 `_eu.py` 模板）
- [ ] 新建 `backend/tests/unit/test_reaper.py`（P1-C6）
- [ ] 新建 `backend/tests/unit/test_daily_archive_job.py`（P1-C6）
- [ ] 跑 `pytest tests/unit/test_saihu_client.py --cov=app.saihu --cov-report=term-missing` 确认 coverage（P2-C3）
- [ ] 补 `test_suggestion_patch.py` 两条 urgent 边界 case（P2-C4）
- [ ] Commit: `test(backend): 补 inventory_eu / reaper / daily_archive / suggestion_patch 边界`

### Task B.4 — 性能零碎（P2-D1 ~ P2-D4）

- [ ] `sync/order_detail.py` 事务粒度查证（P2-D1）：如果 per-row commit 改 batch 每 50 条
- [ ] `frontend/vite.config.ts` `chunkSizeWarningLimit: 1000`（P2-D2）
- [ ] 安装 `rollup-plugin-visualizer` 看 `index-*.js` 内容（P2-D3，可选）
- [ ] 数据页 `el-table` 5000 行启用 `virtual` 属性（P2-D4，仅 `DataOrdersView` / `DataInventoryView` 等大数据页）
- [ ] Commit: `perf: 前后端零碎优化（order_detail batch commit / bundle warn limit / table virtual）`

### Task B.5 — 整洁零碎（P2-E1 + P2-E3）

- [ ] 确认 `deploy/data/pg-local/` 废弃（grep compose 引用）后 `rm -rf` + 加 gitignore（P2-E1）
- [ ] 新建 `docs/superpowers/plans/archived/2026-04/` 把已完成 plan 移入（按年月 / 按 commit 已 merge 判定）
- [ ] `docs/reviews/` 合并到 `docs/superpowers/reviews/`（把 `2026-04-19-full-audit.md` 移过来并删原目录）
- [ ] 更新 `PROGRESS.md` 索引或 AGENTS.md 目录结构
- [ ] Commit: `chore: 清理 deploy/data/pg-local + 归档旧 plans + 合并 docs/reviews/`

### Task B.6 — 前端死代码清理（P1-B9 + 相关）

- [ ] 删除 `frontend/src/utils/allocation.ts` + `allocation.test.ts`
- [ ] 确认后端 `AllocationExplanation` schema 是否仍被 API 返回；若无前端消费位但 API 仍返回，也可一并评估删除（跨前后端决策，需先沟通）
- [ ] Commit: `chore(frontend): 删除 allocation util 死代码`

---

## 全局完成判据

- [ ] 打包 #1 ~ #7 + #BACKLOG 全部 PR 合并
- [ ] 跑一次完整 Stage 0 自动化扫描（见 inventory.md），**所有数据面指标**达标：
  - ruff: 0
  - mypy: 0 errors（strict + 不再有业务模块 override）
  - pytest: 312+ passed / 0 failed / coverage ≥ 75%
  - vue-tsc: 0
  - ESLint: 0 errors
  - vite build: 无 chunk 超限警告（warning limit 已改 1000）
- [ ] 完整 Stage 0 inventory 重新生成一份 `docs/superpowers/reviews/2026-XX-XX-post-audit-inventory.md` 对比修复前后
- [ ] `AGENTS.md` / `PROGRESS.md` / `Blueprint.md` / `spec.md` 无 Plan A 前话术残留
- [ ] `git status` 无未跟踪非代码文件（`cloudflared*` / `.lnk` / 根目录 `.mypy_cache` 全 gitignore）
- [ ] CI pipeline 绿色（backend + frontend + docker-build + publish），且 integration tests 非 skip

---

## 执行协议注记

- **建议用 `superpowers:subagent-driven-development` 驱动**：每个打包由一个 subagent 闭环（拉分支 → 改代码 → 跑测试 → 开 PR → 回报），主会话 orchestrate
- **打包 #2 (mypy 债) 和 #BACKLOG Task B.3 (test 补缺) 相对独立**，可以最早并行启动
- **打包 #3 (历史页去重) 和 #5 (文档漂移) 都涉及大量 context**，适合专人集中做，不要碎片拆
- **打包 #4 (retention)** 需要 DB migration，完成后 dev 容器可能要重跑 `alembic upgrade head`
- **风险点**：打包 #2 的 Task 2.4（删 mypy overrides）可能在删完后暴露尚未清理完的类型错误 — 严格按 "删一个 → 验证 → 再删下一个" 顺序，不批量删
