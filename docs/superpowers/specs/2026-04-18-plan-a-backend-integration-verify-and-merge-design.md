# Plan A 后端集成测试验证 + 合并 master（设计）

- **Date**: 2026-04-18
- **Branch**: `feature/suggestion-export-redesign`
- **Base**: `master`
- **Scope**: 跑真实 Postgres 的集成测试 → 同步关键文档 → 开 PR → `--no-ff` merge

---

## 1. 目标

Plan A 的 18 个后端任务已全部完成（unit 273 绿、mypy 0 错）。但 `backend/tests/integration/**` 里新写的集成测试（snapshot、delete guard、generation-toggle、export e2e 等）在没有 `TEST_DATABASE_URL` 时全部 skip。本次交付目标：

1. 在真实 PostgreSQL 上把集成测试跑通。
2. 同步**进度**与**架构**两份关键文档（其他延后到 Plan B）。
3. 把分支干净合并回 `master`。

## 2. 决策（已与用户确认）

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| Postgres 来源 | 复用 `docker-compose.dev.yml` 的 `restock-dev-db`（宿主 `localhost:5433`），建独立测试库 `replenish_test` | 项目 1-5 人，YAGNI；已有容器直接用，不新增测试 compose |
| 合并路径 | push → 开 PR → 本地 `git merge --no-ff` 落 master | PR 作为可追溯入口；`--no-ff` 保留 18 个 commit 的分支结构与任务粒度 |
| 文档同步范围 | `docs/PROGRESS.md` + `docs/Project_Architecture_Blueprint.md` | 前者是"事实进度"；后者反映模块拓扑变化（删 pushback / 加 snapshot）。API contract、scorecard 等延后到 Plan B 前端对接一起写 |

## 3. 连接参数（已核实）

```
postgresql+asyncpg://postgres:${DB_PASSWORD}@localhost:5433/replenish_test
```

- `DB_PASSWORD` 从 `deploy/.env` 读取，复用现有值。
- `backend/tests/integration/conftest.py` 已硬编码拒绝库名 `replenish`；测试库 `replenish_test` 天然隔离。
- 表结构由 fixture 的 `Base.metadata.create_all/drop_all` 管理 —— 测试库**不走 alembic**，只需数据库壳存在。

## 4. 执行流水线

### 4.1 跑集成测试

```bash
# 1) 准备测试库（DROP IF EXISTS 保证可重入）
docker exec restock-dev-db psql -U postgres -c \
  "DROP DATABASE IF EXISTS replenish_test; CREATE DATABASE replenish_test;"

# 2) 跑集成测试
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://postgres:${DB_PASSWORD}@localhost:5433/replenish_test" \
  python -m pytest tests/integration -v

# 3) 跑 unit 全回归（确认未被干扰）
python -m pytest tests/unit -q

# 4) 清理
docker exec restock-dev-db psql -U postgres -c "DROP DATABASE replenish_test;"
```

### 4.2 同步文档（只动两份）

**`docs/PROGRESS.md`**：
- 顶部"最近更新" → `2026-04-18`。
- 新增一段 Plan A 后端完成摘要：Excel 快照导出、生成开关、推送/Saihu 代码已移除、新增 snapshot/export_log 表。
- 状态表把"补货推送" / "Saihu pushback" 相关行删除或标记 `removed`。

**`docs/Project_Architecture_Blueprint.md`**：
- 领域模型图 / 模块表删除：`pushback/`、`saihu/endpoints/purchase_create.py`、`core/commodity_id.py`。
- 新增：`SuggestionSnapshot` / `SuggestionSnapshotItem` / `ExcelExportLog` 三张表的定位与不可变性约束。
- 状态机：`draft → archived/error`（去掉 `partial/pushed`）。
- 生成开关入口校验链路在 `engine/runner.py:45` 的位置说明。

### 4.3 合并

```bash
# 追加文档同步 commit
git add docs/PROGRESS.md docs/Project_Architecture_Blueprint.md
git commit -m "docs: 同步 Plan A 后端导出重构进度"

# push + PR
git push -u origin feature/suggestion-export-redesign
gh pr create --base master \
  --title "feat: suggestion 导出重构 Plan A 后端" \
  --body "$(cat <<'EOF'
## Summary
- 移除推送/Saihu pushback，改为 Excel 4-Sheet 快照导出（SuggestionSnapshot 不可变）
- 补货建议生成开关（首次导出自动 OFF，管理员 PATCH 翻 ON 归档 draft）
- 引擎入口在开关关闭时短路返回 None

## Test plan
- [x] backend unit 273 绿
- [x] mypy app 0 错
- [x] integration 测试在 replenish_test 库全绿（本地验证）
- [ ] CI 通过（自动）
EOF
)"

# CI 绿后本地合并
git checkout master
git pull
git merge --no-ff feature/suggestion-export-redesign
git push
```

## 5. 失败处理

- **Schema create_all 就炸**：通常是模型字段漏 `server_default` 或约束冲突。→ 修模型 → 第 1 步的 DROP IF EXISTS 保证可重复执行。
- **断言失败**：视为普通 bug fix，**在本分支追加 commit**，不要 `--amend` / force-push，保留任务粒度。
- **CI 报 mypy / ruff / pip-audit**：同上，追加 fix commit。
- **任何一步红 → 不进入下一步**。特别是 integration 未全绿前不碰文档和 PR。

## 6. 成功判据

- [ ] 集成测试在 `replenish_test` 上全绿（含 `test_export_e2e` 闭环）。
- [ ] 单元测试保持 273 绿。
- [ ] `mypy app` 0 错误。
- [ ] 两份文档同步已 commit。
- [ ] PR 已开，GitHub CI 通过（backend + frontend + docker-build 三个 job）。
- [ ] master 已含 `--no-ff` merge commit，工作树干净。

## 7. 非目标（明确排除）

- 不做 Plan B 前端任何改动。
- 不改 CI 配置（不给 GitHub Actions 加真实 Postgres service —— 留给后续单独评审）。
- 不 squash，不 rebase 已存在的 18 个 commit。
- 不回写已推送 suggestion 的 JSONB 快照字段（CLAUDE.md 禁令）。
