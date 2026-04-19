# Plan A 后端集成测试验证 + 合并 master 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在真实 Postgres 上跑 `backend/tests/integration` 全绿，同步进度 + 架构两份关键文档，开 PR 并以 `--no-ff` 合并到 `master`。

**Architecture:** 复用 `docker-compose.dev.yml` 里的 `restock-dev-db` 容器（已在 `localhost:5433` 运行），建独立 `replenish_test` 库；文档层只动 `PROGRESS.md` + `Project_Architecture_Blueprint.md`；合并走 PR + 本地 `--no-ff` merge，保留 18 个 commit 的任务粒度。

**Tech Stack:** PostgreSQL 16 (docker)，pytest + pytest-asyncio，git + gh CLI，Windows git-bash。

**前置事实（已核实）：**

- 容器 `restock-dev-db` 状态 `Up (healthy)`，宿主端口 `5433 → 5432`。
- `deploy/.env.dev` 里 `DB_PASSWORD=local_check_db_password`。
- `backend/tests/integration/conftest.py` 硬拦截库名 `replenish`；`replenish_test` 走 `Base.metadata.create_all/drop_all` 自动建表销表，不跑 alembic。
- 当前分支 `feature/suggestion-export-redesign`，本地已领先 `master` 19 个 commit（18 任务 + 1 spec）。

---

## Task 1: 集成测试在 `replenish_test` 全绿

**目的：** 核心验证 —— Plan A 在真实 Postgres 上没有任何 schema / 行为回归。

**Files:**
- No file changes — ops only

- [ ] **Step 1: 建空测试库（可重入）**

Run:
```bash
docker exec restock-dev-db psql -U postgres -c \
  "DROP DATABASE IF EXISTS replenish_test; CREATE DATABASE replenish_test;"
```

Expected stdout:
```
DROP DATABASE
CREATE DATABASE
```

- [ ] **Step 2: 跑集成测试**

Run:
```bash
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://postgres:local_check_db_password@localhost:5433/replenish_test" \
  python -m pytest tests/integration -v
```

Expected: 所有集成测试 PASS（含 `test_snapshot_api`、`test_suggestion_delete_with_snapshot`、`test_generation_toggle_api`、`test_export_e2e`、`test_engine_e2e`、`test_config_api`、`test_health`），0 failed / 0 errored。

- [ ] **Step 3: 分类处理测试结果**

若全绿 → 直接 Step 4。

若红：
- **schema 层失败**（create_all 就炸）：修模型字段 / 约束 → 回到 Step 1 重跑（DROP IF EXISTS 保证可重入）。
- **断言失败**：当成 bug fix，在本分支 `git add ... && git commit -m "fix(...): ..."` 追加新 commit，**不要 amend / force-push**。修完回到 Step 2。
- **fixture / import 失败**：补 fixture 或更新 `tests/integration/factories.py` 后回到 Step 2。

反复直到 Step 2 全绿为止，才可进入 Step 4。

- [ ] **Step 4: Unit 全回归**

Run:
```bash
cd backend
python -m pytest tests/unit -q
```

Expected: `273 passed` (或至少与合并前一致，不允许下降)。

- [ ] **Step 5: Mypy + Ruff 复查**

Run:
```bash
cd backend
python -m mypy app && python -m ruff check .
```

Expected:
```
Success: no issues found in 105 source files
All checks passed!
```

- [ ] **Step 6: 清理测试库**

Run:
```bash
docker exec restock-dev-db psql -U postgres -c "DROP DATABASE replenish_test;"
```

Expected stdout: `DROP DATABASE`。

- [ ] **Step 7: 本 task 不产生 commit**

Task 1 是纯验证步骤（只有测试红需要修 bug 时才会有 commit，且那些 commit 各自独立命名，不要在这里统一打包）。

---

## Task 2: 同步 `docs/PROGRESS.md`

**目的：** `PROGRESS.md` 是"事实进度看板"，代码已经改完但文档没同步 = 撒谎。本次不改历史段落（那些记录的是历史事实，按协作规范保留），只在顶部 + 近期变更节新增本次交付摘要。

**Files:**
- Modify: `docs/PROGRESS.md`（顶部第 3 行日期 + `## 2. 已交付能力` 下方新增 2.X 小节 + 总体状态表"主链路"一行）

- [ ] **Step 1: 更新顶部"最近更新"日期**

打开 `docs/PROGRESS.md`。把第 3 行：

```markdown
> 最近更新：2026-04-17（大数据页服务端分页已落地，并修复 GHCR 发布链路对大小写仓库 owner 的兼容问题）
```

改为：

```markdown
> 最近更新：2026-04-18（补货建议导出重构 Plan A 后端完成：移除推送/赛狐 pushback，改为 Excel 快照导出 + 不可变 snapshot + 生成总开关）
```

- [ ] **Step 2: 修订"总体状态"表的主链路描述**

找到第 12 行：

```markdown
| 主链路 | 打通 — 赛狐同步 → 补货计算 → 建议编辑 → 采购单推送 |
```

改为：

```markdown
| 主链路 | 打通 — 赛狐同步 → 补货计算 → 建议编辑 → Excel 快照导出（原赛狐采购单推送已下线） |
```

- [ ] **Step 3: 在"## 3. 近期变更"最上方插入新节**

找到 `## 3. 近期变更` 一节标题（具体行号随文件变动，用字符串匹配即可），在它下面紧接着插入：

````markdown
### 3.X 补货建议导出重构 Plan A 后端（2026-04-18）

**动机：** 赛狐推送链路长期维护成本高、失败回放复杂，业务方改为由人工下载 Excel 后在赛狐 web 手工下采购单。

**范围（18 commits on `feature/suggestion-export-redesign`）：**

- **模型层**：新增 `SuggestionSnapshot` / `SuggestionSnapshotItem`（不可变导出快照）+ `ExcelExportLog`（审计）；`Suggestion` 状态枚举收缩为 `draft / archived / error`（去掉 `partial / pushed`）；`SuggestionItem` 去掉 `push_status / push_blocker / commodity_id` 等推送字段，新增 `export_status / exported_snapshot_id / exported_at`；`GlobalConfig` 新增 `suggestion_generation_enabled` + 操作人追踪字段。
- **服务层**：新增 `backend/app/services/excel_export.py`，openpyxl 生成 4-Sheet Workbook（SKU 汇总 / SKU×国家 / SKU×国家×仓库 / 导出元信息）。
- **API 层**：新增 `POST /api/suggestions/{id}/snapshots` / `GET /api/suggestions/{id}/snapshots` / `GET /api/snapshots/{id}` / `GET /api/snapshots/{id}/download`；新增 `GET|PATCH /api/config/generation-toggle`；`POST /api/suggestions/{id}/push` 及 `pushback/purchase.py`、`saihu/endpoints/purchase_create.py`、`core/commodity_id.py` 已删除；`GET /api/suggestions` 注入 `snapshot_count`。
- **引擎入口**：`engine/runner.py` 在加载 GlobalConfig 后立即校验 `suggestion_generation_enabled`，关闭时 `logger.warning` + `progress("补货建议生成已关闭,跳过本次计算")` + 返回 `None`。
- **业务约束**：首次成功导出会自动把 `suggestion_generation_enabled` 翻为 `False`（防止引擎继续生成覆盖），必须由管理员 `PATCH /api/config/generation-toggle {enabled: true}` 手动翻 ON；翻 ON 同时会把所有 `status='draft'` 的旧建议单归档（`archived_trigger='admin_toggle'`）。
- **删除保护**：`DELETE /api/suggestions/{id}` 当 suggestion 已有 snapshot 时返回 409。
- **权限**：新增 `restock:export` / `restock:new_cycle`；旧的 `restock:operate`（推送）字面保留但不再挂端点。
- **Migration**：`20260418_0900_redesign_to_export_model.py` 单 head，包含所有建表 + 字段清理 + 枚举收缩。
- **测试**：unit 273 绿，新增 `test_export_e2e` 闭环集成测试。

**非本次交付（延后到 Plan B 前端）：** Vue 页面改造、前端调用契约迁移、scorecard / API contract 文档同步。

**Migration 向后不兼容：** 已推送（历史 `status='pushed'`）的 suggestion 会被 migration 重写为 `archived`；push 相关字段物理 drop。执行 `alembic upgrade head` 前请先 `pg_backup.sh`。
````

> 如果现有 `## 3. 近期变更` 下小节编号是 `3.30` / `3.31` 这种连续整数，把 `3.X` 替换为下一个可用编号（打开文件最上面找到最大号 + 1）。

- [ ] **Step 4: 验证 markdown 没坏**

Run:
```bash
head -5 docs/PROGRESS.md
```

Expected: 第 3 行显示 2026-04-18 日期 + 新摘要。

---

## Task 3: 同步 `docs/Project_Architecture_Blueprint.md`

**目的：** 架构蓝图反映模块拓扑。本次删除了 `pushback/` / `saihu/endpoints/purchase_create.py` / `core/commodity_id.py`，新增了 `services/excel_export.py` + snapshot 模型，必须同步。

**Files:**
- Modify: `docs/Project_Architecture_Blueprint.md`

- [ ] **Step 1: 定位并修改推送相关段落**

Run:
```bash
grep -n "pushback\|push_saihu\|commodity_id\|purchase_create" docs/Project_Architecture_Blueprint.md
```

对每条命中结果，判断：
- **若是历史事实性描述**（如"曾经的推送链路"）：保留，在同段末尾加一句 `> 注：自 2026-04-18 起，推送链路被移除，改为 Excel 快照导出（见新节"导出快照子系统"）`。
- **若是当前能力描述**（如"推送到赛狐使用 xxx 模块"）：删除整段或改写成"已移除"。

原则：**不追溯改写历史段落，但当前能力描述必须与代码一致**。

- [ ] **Step 2: 在适当位置新增"导出快照子系统"小节**

在架构蓝图"数据模型"或"模块划分"章节（用 `grep -n "^##\|^###" docs/Project_Architecture_Blueprint.md` 找合适位置）新增：

````markdown
### 导出快照子系统（Plan A 后端，2026-04-18）

**模块组成：**

- `backend/app/services/excel_export.py` — 纯函数，openpyxl 生成 4-Sheet Workbook（SKU 汇总 / SKU×国家 / SKU×国家×仓库 / 导出元信息）。
- `backend/app/api/snapshot.py` — 快照 CRUD 端点。
- 表：
  - `suggestion_snapshot` — 主表，与 `suggestion` 是 N:1（一个 suggestion 可导出多版本 snapshot，version 自增）。
  - `suggestion_snapshot_item` — 快照条目，**不可变**（导出瞬间的字段副本，后续对 suggestion_item 的修改不回写）。
  - `excel_export_log` — 下载 / 创建审计。
  - `suggestion_item` 新增 `export_status / exported_snapshot_id / exported_at` 供列表筛选与追溯。

**状态机变化：**

Before：`draft → partial → pushed → archived`（+ `error`）
After：`draft → archived`（+ `error`）。"partial / pushed" 语义由 `suggestion_item.export_status ∈ {pending, exported}` 承载。

**生成开关：**

- `global_config.suggestion_generation_enabled`：由 `engine/runner.py` 入口检查；首次 `POST /api/suggestions/{id}/snapshots` 成功会自动翻为 `false`（防止引擎继续覆盖已导出批次）。
- `PATCH /api/config/generation-toggle {enabled: true}`：管理员手动翻 ON，同时会把所有 `status='draft'` 的旧建议单用 `archived_trigger='admin_toggle'` 归档。

**已删除模块（2026-04-18 起不存在）：**

- `backend/app/pushback/purchase.py`
- `backend/app/saihu/endpoints/purchase_create.py`
- `backend/app/core/commodity_id.py`
- `POST /api/suggestions/{id}/push` 端点

**权限码变化：**

- 新增：`restock:export`（导出 snapshot）、`restock:new_cycle`（翻生成开关）。
- 旧 `restock:operate` 字面保留但不再挂任何端点（暂不移除以免影响现有 RBAC 表）。
````

- [ ] **Step 3: 确认文件仍是合法 markdown**

Run:
```bash
head -20 docs/Project_Architecture_Blueprint.md && tail -20 docs/Project_Architecture_Blueprint.md
```

Expected: 头尾结构未破坏，没有未闭合的代码块栅栏。

---

## Task 4: Commit 文档 + push 分支 + 开 PR

**目的：** 把文档同步作为一个独立 commit，然后 push 并开 PR。

**Files:**
- Modify: `docs/PROGRESS.md`, `docs/Project_Architecture_Blueprint.md`（已在 Task 2/3 改完）

- [ ] **Step 1: 检查待提交文件**

Run:
```bash
git status
git diff --stat docs/
```

Expected: 只有 `docs/PROGRESS.md` 和 `docs/Project_Architecture_Blueprint.md` 被改，且只在"近期变更"/"架构子系统"新增内容 + 顶部日期修订。不应该有任何代码文件变更。

- [ ] **Step 2: 创建文档同步 commit**

Run:
```bash
git add docs/PROGRESS.md docs/Project_Architecture_Blueprint.md
git commit -m "$(cat <<'EOF'
docs: 同步 Plan A 后端导出重构进度

- PROGRESS.md: 顶部日期 + 主链路描述 + 近期变更新增 Plan A 摘要
- Project_Architecture_Blueprint.md: 新增"导出快照子系统"小节,
  标注推送/pushback/saihu 模块已移除
EOF
)"
```

Expected: commit 成功，`1 insertion / 2 files changed` 左右。

- [ ] **Step 3: push 到远程**

Run:
```bash
git push -u origin feature/suggestion-export-redesign
```

Expected: `Branch 'feature/suggestion-export-redesign' set up to track 'origin/feature/suggestion-export-redesign'`。

如果 remote 已存在该分支且超前 → **不要 force-push**。先 `git pull --ff-only`，有冲突则 `git status` 查看并手工解决后 `git push`。

- [ ] **Step 4: 开 PR**

Run:
```bash
gh pr create --base master --title "feat: suggestion 导出重构 Plan A 后端" \
  --body "$(cat <<'EOF'
## Summary
- 移除推送/赛狐 pushback,改为 Excel 4-Sheet 快照导出（SuggestionSnapshot 不可变）
- 补货建议生成开关（首次导出自动 OFF,管理员 PATCH 翻 ON 同时归档 draft）
- 引擎入口在开关关闭时短路返回 None

## Commits
19 个 commit（18 任务 + 1 docs 同步),按任务粒度保留,不 squash。

## Test plan
- [x] backend unit 273 绿
- [x] mypy app 0 错
- [x] integration 测试在 replenish_test 库全绿（本地验证)
- [ ] CI 通过（自动)

## Migration
`20260418_0900` 单 head,包含 push 字段 drop + snapshot/export_log 建表 +
状态枚举收缩。执行 `alembic upgrade head` 前请先 `pg_backup.sh`。

## 非本次交付
Vue 前端改造、scorecard / API contract 文档同步 → 延后到 Plan B。
EOF
)"
```

Expected: 输出 PR URL，形如 `https://github.com/XHBbps/restock_system/pull/NN`。把 URL 记下来备用。

- [ ] **Step 5: 等 CI**

Run:
```bash
gh pr checks --watch
```

Expected: 所有 checks（`backend`、`frontend`、`docker-build`）都 PASS。

若失败：
- **backend 红**：`gh pr checks` → 看详情日志 → 本地复现修 → 追加 commit → `git push`（CI 自动重跑）。
- **frontend 红**：前端未改，理论上不会红；若真红，可能是依赖 lockfile 漂移 → `cd frontend && npm ci`（如有变更需 commit）。
- **docker-build 红**：通常是基础镜像拉取或 Dockerfile 引用路径问题 → 本地 `docker build -t test ./backend` 复现。

---

## Task 5: 合并 master + 清理

**目的：** 本地以 `--no-ff` 合并，保留分支结构。

**Files:**
- No file changes — git ops only

- [ ] **Step 1: 切到 master 并拉新**

Run:
```bash
git checkout master
git pull origin master
```

Expected: `Already up to date` 或拉到远程最新 commit。**若 pull 进来新 commit 导致与本分支有实质冲突 → 停下来 rebase 或 merge master 到 feature 分支，再从 Task 1 重跑回归**，避免把未测试的合并结果直接上主干。

- [ ] **Step 2: 合并 feature 分支**

Run:
```bash
git merge --no-ff feature/suggestion-export-redesign \
  -m "Merge branch 'feature/suggestion-export-redesign' into master

Plan A: suggestion 导出重构后端（19 commits）

详见 docs/superpowers/specs/2026-04-17-suggestion-export-redesign-design.md
"
```

Expected: `Merge made by the 'recursive' strategy.` 并列出变更文件统计。

- [ ] **Step 3: push master**

Run:
```bash
git push origin master
```

Expected: push 成功。GitHub 上 PR 自动变为 `Merged`。

- [ ] **Step 4: 验证最终状态**

Run:
```bash
git log --oneline -25
git status
```

Expected:
- 最上方 1 个 Merge commit + 19 个本次任务 commit
- working tree clean

- [ ] **Step 5: 本地删除 feature 分支（可选）**

用户认为不再需要本地分支时才执行。执行前用 `git branch -vv` 确认 remote tracking 已同步：

Run:
```bash
git branch -d feature/suggestion-export-redesign
```

Expected: `Deleted branch feature/suggestion-export-redesign`。如果 git 提示未合并 → **不要改用 `-D`**，先用 `git log master..feature/...` 看看遗漏了什么。

远程分支保留与否：GitHub 上可按需 `Delete branch` 按钮，或用 `git push origin --delete feature/suggestion-export-redesign`。内部分支 1-5 人团队通常保留一段时间做回溯。

---

## 附录 A: 失败兜底清单

| 失败位置 | 处理 |
| --- | --- |
| Task 1 Step 2 测试红 | 在本分支追加 fix commit,不 amend,回到 Step 2 |
| Task 1 Step 4 unit 回归红 | 上一步修复引入新问题,追加 commit |
| Task 2/3 发现文档原有错误不是本次造成 | 不修,只管本次 scope;在 PR 描述里留 note 让后续任务跟进 |
| Task 4 Step 3 push 被拒（non-fast-forward） | `git pull --ff-only`,有冲突解决后再 push;**禁止 force-push** |
| Task 4 Step 5 CI 红 | 按具体 job 类型处理,追加 commit,CI 自动重跑 |
| Task 5 Step 1 master 被人动过 | 停,先 rebase feature onto master,重跑 Task 1 回归 |
| 任何阶段发现 spec 有漏洞 | 停下来,先更新 spec(`docs/superpowers/specs/2026-04-18-...-design.md`),再继续 |

## 附录 B: 完成自检

- [ ] 集成测试在 `replenish_test` 上全绿（含 `test_export_e2e` 闭环）。
- [ ] 单元测试保持 273 绿。
- [ ] `mypy app` 0 错误；`ruff check` pass。
- [ ] `docs/PROGRESS.md` + `docs/Project_Architecture_Blueprint.md` 已 commit。
- [ ] PR 已开,GitHub CI 三个 job 全绿。
- [ ] master 已含 `--no-ff` merge commit,本地 `git status` 干净。
- [ ] `docs/superpowers/plans/2026-04-18-...md` 全部 checkbox 勾选。
