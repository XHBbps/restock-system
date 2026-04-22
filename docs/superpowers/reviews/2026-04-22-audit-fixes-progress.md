# 2026-04-22 Audit Fix 进度快照

> 给**新会话**的交接快照：本文件描述到 2026-04-22 session 1 结束时的修复状态，列出剩余任务 + 新会话接手的无缝启动步骤。

---

## 一、已闭环（18 commits）

### 打包 #1 — P0 闪电修 ✅ 全部完成 + pytest 验证通过

| commit | 内容 | 关闭 |
|---|---|---|
| `a3db867` | engine step4 clamp `purchase_qty >= 0` + DB CheckConstraint + migration `20260422_1000` | P0-1 |
| `af38568` | `docs_enabled()` production 强制忽略 `APP_DOCS_ENABLED` env | P0-2 |
| `50d29cf` | `.github/workflows/ci.yml` 加 postgres service + `TEST_DATABASE_URL` | P0-3 |
| `2d6e6f0` | `.gitignore` 补 `*.exe` / `*.lnk` / `cloudflared*` | P0-4 |

**pytest 验证（最终 clean run）**：**312 passed / 0 failed / 8:48**（`TEST_DATABASE_URL=postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test` 命令见 `inventory.md`）。相较 Stage 0 基线（309 passed, 1 failed）：
- `test_docs_disabled_by_default_in_production` 修复（P0-2 闭环）
- 新增 `test_docs_forced_off_in_production_even_if_env_tries_to_enable`
- 新增 `test_docs_enabled_in_dev_by_default`
- 重命名 `test_step4_clamps_negative_purchase_qty_to_zero`（原 `test_step4_allows_negative_purchase_qty` 断言翻转）

### 打包 #2 — mypy 类型债（部分完成）

| commit | 内容 | 关闭 |
|---|---|---|
| `4c93538` | `api/suggestion.py:45` sort_map 类型 `tuple[Any, ...]`（两次迭代：先 `ColumnElement[Any]` 发现 InstrumentedAttribute 不协变，改 `Any`） | P1-A2 |
| `164a6ba` | `api/monitor.py` Row 明确 tuple 类型 + 去 `# type: ignore[assignment]` | P1-A3 |
| `044c7fe` | `Result.rowcount` / `on_conflict_do_update` / `marketplace_to_country` arg / `dict(Sequence[Row])` / step6_timing 参数 / scheduler `isoformat` 共 8 处精准 ignore / 参数收敛 | P1-A4 |
| `0337c0d` | pyproject.toml 从 override 列表永久删 4 模块（inventory / order_list / daily_archive / scheduler），剩 13 模块作 backlog | P1-C3 部分 |

### 打包 #5 — 文档漂移收口 ✅ 全部

| commit | 内容 | 关闭 |
|---|---|---|
| `324783b` | `AGENTS.md:17 + §11` 推送→导出 | P1-C2 |
| `71ad380` | `PROGRESS.md` estock typo + calc_enabled 残留 + step4 公式 + 最近更新日期 | P2-C1 / P2-C2 |
| `b530bab` | `specs/001-saihu-replenishment/spec.md` Superseded 标签 | P1-C1 |
| `f523dc0` | `Project_Architecture_Blueprint.md` 加变更记录段 | P1-C7 |
| `27c3fad` | `onboarding.md` / `deployment.md` / `runbook.md` 扫尾 | Task 5.5 |

### 打包 #6 — CI 安全网 ✅ 全部

| commit | 内容 | 关闭 |
|---|---|---|
| `ed2ccb9` | `ci.yml` frontend 加 `npm run lint` + 修 `DataInventoryView.test.ts:61` 2 条 `no-useless-escape` | P1-C4 / P2-B5 |
| `03c1b73` | `deploy.yml` production environment（reviewer approval） | P1-E4 |

### 打包 #7 — 部署安全加固 ✅ 全部

| commit | 内容 | 关闭 |
|---|---|---|
| `b494d93` | `Caddyfile` HSTS 加 `preload` | P1-E3 |
| `d7fedec` | `validate_env.sh` 补 JWT 长度 + `app/config.py` 默认占位符 + SAIHU 空白兜底；`deploy.sh` `|| exit 1` | P1-E5 |
| `dc21ef7` | `rollback.sh` 指向 runbook + `runbook.md` 补回滚 SOP 小节 | P2-E2 |

---

## 二、问题闭环统计

| 严重度 | 原总数 | 已闭环 | 剩余 |
|---|---|---|---|
| Critical | 5 | **5** | 0 |
| Important | 37 | ~20 | ~17 |
| Minor | 21 | ~8 | ~13 |

---

## 三、剩余任务（新会话接手）

### 打包 #3 — 历史页去重 + status_code 化（预计 1-2h）
**分支**：`feature/audit-fixes-history-dedup`（新开，rebase 自当前 HEAD）
**涉及文件**：
- 后端：`backend/app/schemas/suggestion.py`、`backend/app/api/suggestion.py`（加 `status_code` 字段）
- 前端：新建 `frontend/src/views/history/SuggestionHistoryView.vue`；改 `ProcurementHistoryView.vue` / `RestockHistoryView.vue` 为薄 wrapper
- 测试：`frontend/src/views/history/__tests__/SuggestionHistoryView.test.ts`

**Task 拆解见 `docs/superpowers/plans/2026-04-22-audit-fixes.md` 的 "打包 #3" 章节**（Task 3.1-3.4）。

### 打包 #4 — retention 三连 + Dashboard 自动失效（预计 2-3h）
**分支**：`feature/audit-fixes-retention`
**涉及文件**：
- 后端：新建 `backend/app/tasks/jobs/retention.py`；改 `backend/app/api/snapshot.py`（410 Gone）+ `backend/app/models/dashboard_snapshot.py`（`stale` 字段）+ `backend/app/api/config.py`（改动触发 stale）+ `backend/app/api/metrics.py`（stale 时自动 enqueue 刷新）
- 迁移：新 alembic migration `YYYYMMDD_dashboard_snapshot_stale + excel_export_log_file_purged_at`
- 测试：`backend/tests/unit/test_retention_job.py`、integration `test_metrics_snapshot_api.py`

**Task 拆解见 plan 的 "打包 #4" 章节**（Task 4.1-4.4）。

### 打包 #BACKLOG — P2 杂项（预计 2-3h）
**分支**：`chore/audit-fixes-p2-misc`
**包含**：
- 后端：`core/locks.py` 常量化（A #4）、`patch_item updates` TypedDict（A #10）、引擎 dict → dataclass（A #11，大改可单独 PR）
- 前端：toolbar wrapper 对齐（B #7）、PurchaseDateCell "6 档" 注释（B #9）、delete 按钮 token（B #11）、文案空格（B #12）、`allocation.ts` 死代码删除（B #13）、`totalSnapshotCount` 内联（B #15）、`RestockListView.editable` 文档 hint（B #16）
- 测试：新建 `test_sync_inventory_eu.py`（C #8）、`test_reaper.py` + `test_daily_archive_job.py`（C #9）、`test_saihu_client` coverage 查证（C #10）、`test_suggestion_patch` 边界（C #11）
- 性能：`sync/order_detail.py` 事务粒度（D #5）、`chunkSizeWarningLimit: 1000`（D #7）、bundle visualizer（D #8）、`el-table virtual`（D #9）
- 整洁：`deploy/data/pg-local/` 废弃判定（E #4）、`docs/reviews/` 合并（E #3）、`plans/archived/`（E #9）

**Task 拆解见 plan 的 "打包 #BACKLOG" 章节**（Task B.1-B.5）。

### 打包 #2 剩余 — 13 模块 blanket override 逐个清理（预计 1-2 天，独立 backlog）
**分支**：`chore/audit-fixes-mypy-debt-2`
**涉及**：
- `app.api.suggestion` / `app.api.monitor` / `app.sync.order_detail` 已部分清理但有 untyped-def 待补 return type 注解
- `app.api.data` / `config` / `task` / `auth` / `sync.out_records` / `sync.warehouse` / `sync.shop` / `tasks.queue` / `saihu.token` / `saihu.client` 未整改

**推荐节奏**：一次删 1-2 个模块 + 验证 + commit，累计到所有删完。

---

## 四、新会话接手步骤

1. **读必读上下文**（按顺序）：
   - `docs/superpowers/reviews/2026-04-21-session-context.md`（项目背景）
   - `docs/superpowers/reviews/2026-04-21-inventory.md`（Stage 0 + 推荐 pytest 命令）
   - `docs/superpowers/reviews/2026-04-21-full-audit.md`（Stage 2 优先级矩阵）
   - `docs/superpowers/plans/2026-04-22-audit-fixes.md`（Stage 3 plan，各打包 Task 细节）
   - **本文件**（进度快照）

2. **确认分支和状态**：
   ```bash
   git log --oneline 0337c0d~20..0337c0d   # 看 Stage 3 的 18 个 commit
   git log --oneline master..HEAD           # 整个 feature 分支的 commit 数（预期 69+）
   git status                                # 应只有 docs/reviews/ untracked
   ```

3. **确认 dev 环境**：
   ```bash
   docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev ps
   ```
   6 个容器应 healthy。如容器 image 过旧可重新 build：
   ```bash
   docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev build backend worker scheduler
   docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev up -d backend worker scheduler
   ```

4. **验证基线（可选但推荐）**：
   ```bash
   # 完整 pytest（8-9 min）
   docker exec --user root restock-dev-backend rm -rf /tmp/tests /tmp/pytest_cache
   MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)" restock-dev-backend:/tmp/tests
   MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "
     cd /tmp && \
     TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' \
     COVERAGE_FILE=/tmp/.coverage \
     PYTHONPATH=/app:/install/lib/python3.11/site-packages \
     /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache \
       tests -q --no-header
   "
   # 预期：312 passed / 0 failed / 8-9 min
   ```

5. **挑打包开工**：建议顺序 **#3 → #4 → #BACKLOG → #2 backlog**
   - #3 相对小，1-2h 能出一个 PR 量级的闭环
   - #4 涉及 migration，需要 dev DB 干净（可 `docker exec restock-dev-db psql -U postgres -c "DROP DATABASE IF EXISTS replenish_test; CREATE DATABASE replenish_test;"` 重置）
   - #BACKLOG 最杂，可以再拆分多个 commit / PR
   - #2 剩余 13 模块的 blanket override 是**最花时间的**部分，建议最后做

6. **commit 风格遵循已落地的 18 条**：`<scope>: <短标题>` + body 解释"为什么"+ `Close PX-XX from docs/superpowers/reviews/2026-04-21-full-audit.md`

---

## 五、已知坑位（节省新会话时间）

- **docker cp `backend/tests` 在 Git Bash 下会创建 `/tmp/tests/tests/` 嵌套目录**（原因未知，MSYS 路径翻译疑似 bug）
  - 解法：用 `MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)" ...` 绝对路径 + 先 `docker exec --user root ... rm -rf /tmp/tests` 清理
- **pytest 双重 collection 检查**：tests collected 显示 312 则正常，624 说明有 `/tmp/tests/tests/` 残留
- **docker exec 默认以 `app` 用户运行**，`/app` 下不可写；改 `/app/app/*.py` 或 alembic 版本文件要用 `docker cp ...:/app/...`（docker cp 以 root 跑）
- **打包 #2 Task 2.4 的陷阱**：`InstrumentedAttribute[T]` 在 mypy 视角**既不是** `ColumnElement[T]` 子类**也不协变**；用 `tuple[Any, ...]` 才是最安全宽松声明
- **pytest 单次 8-9 min**：避免连续跑多次；如果只测改动模块用 `pytest tests/unit/test_xxx.py`（~5s）
- **打包 #3 后端 schema 改动会破坏前端**：必须前后端同步改 + 同 PR 合入；否则可能要 DB migration 回滚

---

## 六、给用户的提醒

- 当前分支 `feature/split-procurement-restock-and-eu` 现已达 **69+ commits ahead of master**，建议在继续前考虑：
  - 要不要把 Stage 3 前 18 个 audit fix commits 先拆独立 PR 合入 master，再继续 #3 / #4 / #BACKLOG
  - 或者保留在同一 feature branch，等 #3 / #4 / #BACKLOG 全部完成后一次性合入（risk：分支太大 review 困难）
- `docs/reviews/` 目录（legacy 只有 `2026-04-19-full-audit.md`）仍未处理，归 #BACKLOG Task B.5
