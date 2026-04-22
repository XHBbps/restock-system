# 2026-04-21 全量 Review 汇总（Stage 2 合并报告）

> 本文档合并 Stage 1 五份分域审计（Agent A/B/C/D/E），按严重度去重 + 用 2D 矩阵排优先级。
> 源报告：`agent-A-backend.md` / `agent-B-frontend.md` / `agent-C-completeness.md` / `agent-D-performance.md` / `agent-E-deploy.md`

---

## 统计

| 严重度 | 条数 | 占比 |
|---|---|---|
| Critical | **5** | 8% |
| Important | **37** | 59% |
| Minor | **21** | 33% |
| **总计** | **63** | 100% |

按域分布：
- 后端代码（Agent A）：14 条
- 前端 UX（Agent B）：16 条
- 完整度/测试/文档（Agent C）：13 条
- 性能（Agent D）：11 条
- 部署/整洁（Agent E）：9 条

信息项（已验证无问题，不进优先级矩阵）：A#3/#12/#13/#14、D#4/#6/#10/#11、C#13 共 9 条（不计入 63）。

---

## 优先级规则

- **P0**（本周必修）：Critical + 工作量 S / M
- **P1**（2 周内）：Important + 工作量 S / M；或 Critical + 工作量 L
- **P2**（backlog）：Minor 任意工作量；或 Important + 工作量 L
- **P3**（放弃 / 价值不明）：无

---

## P0 清单（本周必修）— 4 条

| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P0-1 | **`purchase_qty` 引擎可返负数、DB 无 CheckConstraint** | `backend/app/engine/step4_total.py:55-66` + `backend/app/models/suggestion.py:77-102` | S | Agent A #1 |
| P0-2 | **`docs_enabled()` production 可被 `APP_DOCS_ENABLED=true` env 穿透** | `backend/app/config.py:24,69-72` | S | Agent A #2 |
| P0-3 | **CI 从未真正运行 integration tests**（28 条被静默 skip） | `.github/workflows/ci.yml:31-32` + `backend/tests/conftest.py:18-24` | M | Agent C #5 |
| P0-4 | **`cloudflared-windows-amd64.exe`（65 MB）未进 .gitignore**，误 commit 炸仓库 | 根目录 + `.gitignore` | S | Agent E #1 |

**P0 关联关系**：
- P0-1 在"真实业务 bug"里最严重 — 负数 `purchase_qty` 会流入前端显示与 Excel 导出
- P0-2 是 Stage 0 唯一真实测试失败的根因，修好之后 pytest 312/0
- P0-3 + P1 的 C#6 联动：CI 跑不到 integration → 业务回归无保障；mypy override → 真类型 bug 不报
- P0-4 纯防御性，1 行 .gitignore 修完

---

## P1 清单（2 周内）— 28 条

### 后端代码（4 条）

| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P1-A1 | `api/suggestion.py` 399 行单文件，拆 `api/suggestion/` 包 | `backend/app/api/suggestion.py` | M | A #5 |
| P1-A2 | 排序 sort_map 类型声明不协变（mypy 5 条 dict_item） | `backend/app/api/suggestion.py:45-54` | S | A #6 |
| P1-A3 | `api/monitor.py` 把 Row 当 ApiCallLog 存 dict，2 条 index 错误 | `backend/app/api/monitor.py:107,116-117` | S | A #7 |
| P1-A4 | mypy 其他 ~40 条 SQLAlchemy 2.x 类型问题精准 ignore | 多文件 | M | A #8 |

### 前端 UX（9 条）

| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P1-B1 | 采购/补货历史页 95% 重复，抽共用组件 / composable | `frontend/src/views/history/{Procurement,Restock}HistoryView.vue` | M | B #1 |
| P1-B2 | `statusTagType` 用中文字面量匹配（fragile） | 历史两页 `:79-85` | S | B #2 |
| P1-B3 | 对话框关闭按钮样式不一致（`SuggestionDetailDialog` 独有自定义 ×） | `frontend/src/components/SuggestionDetailDialog.vue:7,26-34` | M | B #3 |
| P1-B4 | 详情弹框 `max-height="500"` / `width="80%"` 硬编码无响应式 | `frontend/src/components/SuggestionDetailDialog.vue:5,91,112` | S | B #4 |
| P1-B5 | `DataInventoryView` placeholder 暴露后端字段名 "commoditySku" | `frontend/src/views/data/DataInventoryView.vue:6` | S | B #5 |
| P1-B6 | 发起页 empty 同文案（整单空 vs 筛选空无法区分） | `frontend/src/views/suggestion/{Procurement,Restock}ListView.vue:4,26,32` | S | B #6 |
| P1-B7 | 发起页 `el-table` 未固定"状态"/"操作"列 | `frontend/src/views/suggestion/*.vue` | S | B #8 |
| P1-B8 | 数据页 filter 固定宽度缺响应式（窄屏溢出） | `frontend/src/views/data/*.vue` | M | B #10 |
| P1-B9 | `frontend/src/utils/allocation.ts` 整文件死代码 | `frontend/src/utils/allocation.ts` | S | B #13 |

### 完整度 / 测试缺口 / 文档（7 条）

| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P1-C1 | `spec.md` stale（推送赛狐话术），加 Superseded 标签或重写 | `specs/001-saihu-replenishment/spec.md` | S | C #1 |
| P1-C2 | `AGENTS.md §1 / §11` 仍写"推送采购单回赛狐"、"除推送采购单" | `AGENTS.md:17` + §11 | S | C #2 |
| P1-C3 | **mypy 15 个模块 blanket 抑制真实类型错误**（遮蔽 P0-A 的真 bug） | `backend/pyproject.toml:140-169` | L | C #6 |
| P1-C4 | CI frontend job 未跑 `npm run lint`（Stage 0 eslint error 就是这么合并的） | `.github/workflows/ci.yml:40-59` | S | C #7 |
| P1-C5 | `test_sync_inventory_eu.py` 缺失（4 个 sync 入口只测了 3 个 EU 路径） | `backend/tests/unit/` | S | C #8 |
| P1-C6 | `test_reaper.py` / `test_daily_archive_job.py` 缺失（生产关键后台逻辑） | `backend/tests/unit/` | M | C #9 |
| P1-C7 | `Project_Architecture_Blueprint.md` 可能含推送残留，对照代码复核 | `docs/Project_Architecture_Blueprint.md` | M | C #12 |

### 性能（3 条）

| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P1-D1 | `task_run` / `inventory_snapshot_history` retention 机制缺失（增长型表） | `backend/app/tasks/jobs/` | M | D #1 |
| P1-D2 | `deploy/data/exports/*.xlsx` 累积无清理（每天 5-20 份，年 GB 级） | `backend/app/services/excel_export.py` + 新任务 | M | D #2 |
| P1-D3 | `dashboard_snapshot.payload` 无自动失效（改 EU / restock_regions 后仍展示旧数据） | `backend/app/api/metrics.py` + `config.py` 联动 | M | D #3 |

### 部署 / 整洁（5 条）

| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P1-E1 | 根目录 `.mypy_cache/`（60 MB）+ `backend/.mypy_cache/`（20 MB）未显式 gitignore | `.gitignore` | S | E #2 |
| P1-E2 | `docs/reviews/` vs `docs/superpowers/reviews/` 目录冲突 | `docs/reviews/` | S | E #3 |
| P1-E3 | Caddyfile HSTS 缺 `preload` + Cookie Secure/HttpOnly/SameSite 未配 | `deploy/Caddyfile` | M | E #5 |
| P1-E4 | `deploy.yml` `workflow_dispatch` 绕过 PR review 风险 | `.github/workflows/deploy.yml:41-49` | M | E #6 |
| P1-E5 | 生产 docker-compose 敏感 env 无 `validate_env.sh` 预检（JWT_SECRET 等校验） | `deploy/scripts/` + `deploy/docker-compose.yml` | M | E #8 |

---

## P2 清单（backlog）— 25 条

### 后端（3 条）
| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P2-A1 | advisory lock key `7429001` magic number 无注释，改集中 `core/locks.py` | `backend/app/engine/runner.py:32,40` | S | A #4 |
| P2-A2 | `api/monitor.py:85-105` 原生 `text()` SQL 改写为 SQLAlchemy Core | `backend/app/api/monitor.py` | M | A #9 |
| P2-A3 | `patch_item` `updates: dict[str, Any]` → TypedDict | `backend/app/api/suggestion.py:237` | S | A #10 |
| P2-A4 | 引擎数据结构三层 dict 嵌套 → dataclass / TypedDict | engine/step3-5 全链路 | M | A #11 |

### 前端（10 条）
| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P2-B1 | 发起页 toolbar `__filters` wrapper 结构不对称 | `frontend/src/views/suggestion/*.vue` | S | B #7 |
| P2-B2 | `PurchaseDateCell` 文档"5 档"实际 6 档 | `frontend/src/components/PurchaseDateCell.vue:46-52` + session-context | S | B #9 |
| P2-B3 | 历史页 delete 按钮硬编码色值 `#b91c1c` → 走 design token | `frontend/src/views/history/*.vue:196-201` | S | B #11 |
| P2-B4 | 文案空格/用词细节不统一（"至少6位" vs "至少 6 位"） | 全局 | S | B #12 |
| P2-B5 | `DataInventoryView.test.ts:61` 2 条 `no-useless-escape` eslint error | `frontend/src/views/__tests__/DataInventoryView.test.ts:61` | S | B #14 |
| P2-B6 | `SuggestionListView.totalSnapshotCount` 单处使用可内联 | `frontend/src/views/SuggestionListView.vue:115-119` | S | B #15 |
| P2-B7 | `RestockListView.editable` 声明但无编辑 UI，心智与实际不一致 | `frontend/src/views/suggestion/RestockListView.vue:169` | S | B #16 |

### 完整度 / 文档（4 条）
| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P2-C1 | `PROGRESS.md` 多处 `estock_item_count` typo + `calc_enabled` 残留 | `docs/PROGRESS.md:45,55,79,116` | S | C #3 |
| P2-C2 | `PROGRESS.md §2.3` step4 公式描述过期（缺 safety_stock_days） | `docs/PROGRESS.md:61` | S | C #4 |
| P2-C3 | `app/saihu/client.py` 0% coverage 查证（可能 mock 路径） | `backend/tests/unit/test_saihu_*.py` | S | C #10 |
| P2-C4 | `patch_item` urgent 重算边界 test（空 country / lead_time fallback） | `backend/tests/unit/test_suggestion_patch.py` | S | C #11 |

### 性能（5 条）
| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P2-D1 | `sync/order_detail.py` 事务粒度查证（可能 per-row commit） | `backend/app/sync/order_detail.py` | S | D #5 |
| P2-D2 | Bundle chunk 警告（`chunkSizeWarningLimit: 1000`） | `frontend/vite.config.ts:48` | S | D #7 |
| P2-D3 | 主 entry `index-*.js 55 KB` 来源用 `rollup-plugin-visualizer` 查证 | `frontend/vite.config.ts` | S | D #8 |
| P2-D4 | `el-table` 5000 行启用 virtual scroll | 数据页各 `*View.vue` | M | D #9 |

### 部署 / 整洁（3 条）
| # | 问题 | 位置 | 工作量 | 来源 |
|---|---|---|---|---|
| P2-E1 | `deploy/data/pg-local/` 73 MB 废弃确认 + 删除或 gitignore | `deploy/data/pg-local/` | S | E #4 |
| P2-E2 | `deploy/scripts/deploy.sh` 备份验证 + 模拟回滚演练 | `deploy/scripts/deploy.sh:57` + `rollback.sh` | L | E #7 |
| P2-E3 | `docs/superpowers/plans/` 35+ 已完成 plan 归档 | `docs/superpowers/plans/` | S | E #9 |

---

## 按域分类索引

| 域 | P0 | P1 | P2 |
|---|---|---|---|
| **功能完整度 / 业务正确性** | P0-1, P0-2 | P1-B1, P1-B6 | — |
| **核心链路（引擎 / API）** | P0-1, P0-2 | P1-A1~A4 | P2-A1~A4 |
| **前端 UX** | — | P1-B1~B9 | P2-B1~B7 |
| **性能（后端）** | — | P1-D1, P1-D2, P1-D3 | P2-D1 |
| **性能（前端）** | — | — | P2-D2, P2-D3, P2-D4 |
| **技术债（类型 / 文档）** | — | P1-A4, P1-C3, P1-C7 | P2-A4, P2-C1, P2-C2 |
| **测试缺口 / CI** | P0-3 | P1-C4, P1-C5, P1-C6 | P2-C3, P2-C4 |
| **部署 / 回滚 / 安全** | P0-4 | P1-E3, P1-E4, P1-E5 | P2-E2 |
| **仓库整洁 / 文档漂移** | — | P1-C1, P1-C2, P1-E1, P1-E2 | P2-C1, P2-C2, P2-E1, P2-E3 |
| **死代码** | — | P1-B9 | — |

---

## 跨 agent 关联的"组合修复"建议

Stage 3 做 fix plan 时建议按**主题**打包，避免零散 commit：

### 打包 #1 — P0 闪电修（1 个 commit / 半天）
- P0-1 + P0-2 + P0-4：工程代码（compute_total clamp + docs_enabled 硬编码 production 优先 + .gitignore 补 `*.exe` `*.lnk`）
- P0-3：CI 加 postgres service + `TEST_DATABASE_URL` 单独一个 commit（改 .github/workflows）
- **影响**：一个工作日内把 5 条 Critical 里 4 条闭环

### 打包 #2 — mypy 类型债集中整改（P0-A + P1-A2 + P1-A3 + P1-A4 + P1-C3）
- 先修 `api/suggestion.py:46-50`（P1-A2）和 `api/monitor.py:107,116-117`（P1-A3）
- 再扫 SQLAlchemy 2.x 的 `Result.rowcount` / `on_conflict_do_update` 精准 ignore（P1-A4）
- 最后**逐模块**删掉 `pyproject.toml` 的 blanket override（P1-C3）
- **理由**：P1-C3 是 root cause（遮盖 bug），但直接删会暴露一大片，先消化 A2/A3/A4 再动 C3

### 打包 #3 — 历史页去重 + 状态 code 化（P1-B1 + P1-B2）
- 抽 `SuggestionHistoryView.vue` 共用组件
- 配合后端 `status_code` 枚举（后端 schema 改动 + 前端消费）
- **理由**：两条都涉及历史页，且 B2 需后端配合，一起做避免来回

### 打包 #4 — 数据保留三连（P1-D1 + P1-D2 + P1-D3）
- 新建 `app/tasks/jobs/retention.py` 统一处理 `task_run` / `inventory_snapshot_history` / `exports/*.xlsx`
- Dashboard snapshot 自动失效加到同一提交
- **理由**：都是"增长型资源管理"主题，调度接入同一个 cron

### 打包 #5 — 文档漂移收口（P1-C1 + P1-C2 + P1-C7 + P2-C1 + P2-C2）
- `spec.md` 加 Superseded 标签
- `AGENTS.md §1 / §11` 推送→导出
- `Project_Architecture_Blueprint.md` 逐节复核
- `PROGRESS.md` 修 `estock` typo + `calc_enabled` 残留 + step4 公式更新
- **理由**：都是"照着 Plan A 后收口文档"，批量改一次对齐

### 打包 #6 — CI 安全网补全（P0-3 + P1-C4 + P1-E4）
- `ci.yml` 加 postgres service + TEST_DATABASE_URL（P0-3，已在闪电修里）
- `ci.yml` frontend job 加 `npm run lint`（P1-C4）
- `deploy.yml` 加 branch protection 检查 / environment approval（P1-E4）
- **理由**：都是 CI/CD 守门人，一次 PR 把 workflow 该补的都补了

### 打包 #7 — 部署安全加固（P1-E3 + P1-E5）
- Caddyfile HSTS preload + Cookie Secure（E3）
- `validate_env.sh` 补 JWT_SECRET / login_password / saihu_* 生产校验（E5）
- **理由**：都是"生产启动前必须通过"的硬检查，放一起

---

## Stage 3 决策建议

**推荐接下来立即行动**：
1. 把**打包 #1（P0 闪电修）** 当天做掉 — 4 条 Critical 全闭，仅影响 backend Dockerfile 已独立、engine/step4、config.py、.gitignore、.github/workflows，是低耦合的小改动
2. 然后按**打包 #2~#7** 的顺序作为 2 周 sprint 内容推进（每包可单独开 branch + PR）

**可延后或放弃**：
- P2 全部 25 条作为 backlog，随便什么时候顺手带上；不单独排 sprint
- Agent B 的文案/空格级问题（P2-B4）可在 linter rule 里配置后一次性修

**需要澄清**：
- P1-E4（workflow_dispatch 绕过 PR）是否保留作为应急手段 — 用户策略决定
- P1-C3（mypy override 清理）是否接受"临时 L 工作量"完整做掉，还是分期逐模块下线 — 工程管理决定

用户拍板"立刻做 P0 / 先 P0+P1 / 全量做" 后进 Stage 3 写 `docs/superpowers/plans/2026-04-22-audit-fixes.md`。
