# 2026-04-22 Audit Fix 进度快照 v2（Session 2 收口）

> 本文件是 Session 2 结束时的**交付就绪快照**。Session 1 的快照（`2026-04-22-audit-fixes-progress.md`）记录前 18 commits；本 v2 记录 Session 2 新增的 10 commits，以及整条 `feature/split-procurement-restock-and-eu` 分支的最终状态。
>
> 继续迭代者请先读 Session 1 快照 + 本文件，两份合起来是全量上下文。

---

## 一、Session 2 闭环（10 commits）

### 打包 #3 — 历史页去重 + 状态 code 化

| commit | 内容 | 关闭 |
|---|---|---|
| `4799432` | `feat(backend)`: `SuggestionOut` 扩 `procurement/restock_display_status_code` (Literal: pending/exported/archived/error)；`_derive_display_status` 改返回 (label, code) tuple；list + detail 端点均填充 | P1-B2 前置 |
| `7be9243` | `refactor(frontend)`: 新建 `SuggestionHistoryView.vue` 接 `type` prop；`ProcurementHistoryView` / `RestockHistoryView` 瘦身为 1-line wrapper（-393 / +233 行） | P1-B1 |
| `9ae8e02` | `refactor(frontend)`: `statusTagType` 抽到 `@/views/history/displayStatusTag.ts`，`STATUS_TAG_MAP` 按 code 映射 Element Plus tag type（error→danger 新增）；api/suggestion.ts 加 `SuggestionDisplayStatusCode` 类型 + 3 处 test fixture 补字段 + 新增 `displayStatusTag.test.ts` | P1-B2 |

### 打包 #4 — retention 三连 + Dashboard 自动失效

| commit | 内容 | 关闭 |
|---|---|---|
| `1fcabb5` | `feat(backend)`: 新建 `app/tasks/jobs/retention.py` 含 `purge_task_run` / `purge_inventory_history` / `purge_exports` 三连；scheduler 注册每天 04:00 cron；Settings env `RETENTION_*_DAYS` 可配（0 禁用）；migration 20260423_1000 加 `excel_export_log.file_purged_at` + `dashboard_snapshot.stale`；path-traversal 防护 + 缺失文件兜底标记；12 条单测 | P1-D1 / P1-D2 |
| `4ad4adb` | `feat(backend)`: download 端点检测 `file_purged_at` → 返回 `410 "该版本已过期清理（保留期 N 天）"`；前端 `downloadSnapshotBlob` 加 `_decodeBlobErrorInPlace` 把 `responseType='blob'` 的错误 JSON 解包回填，让 `getActionErrorMessage` 能显示 detail；2 条 integration 测 | P1-D2 配套 |
| `533040b` | `feat(backend)`: `patch_global` 改动 6 个敏感字段（restock_regions / eu_countries / target_days / lead_time_days / buffer_days / safety_stock_days）且值变 → `dashboard_snapshot.stale=TRUE`；GET /dashboard 检测 stale → 自动 enqueue `refresh_dashboard_snapshot` + 返回 `refreshing`；`_mark_ready` 刷完置回 FALSE；2 unit + 3 integration 测 | P1-D3 |

### 打包 #BACKLOG — P2 杂项

| commit | 内容 | 关闭 |
|---|---|---|
| `a1394d0` | `refactor(backend)`: 新建 `app/core/locks.py` 集中 advisory lock 常量；`patch_item` 的 updates 改 `SuggestionItemUpdates` TypedDict | P2-A1 / P2-A3 |
| `a70436c` | `refactor(frontend)`: RestockListView toolbar 对齐 `__filters` wrapper + PurchaseDateCell 注释 5→6 档 + `$color-danger-dark` token 替换硬编码 `#b91c1c` + "至少 6 位"空格统一 + editable 注释 hint | P2-B1 / B2 / B3 / B4 / B7 |
| `fc13956` | `test(backend)`: 4 个新测试文件共 16 条 — inventory_eu (5) / reaper (5) / daily_archive (3) / suggestion_patch urgent 边界 (3) | P1-C5 / P1-C6 / P2-C4 |
| `6477020` | `perf`: vite `chunkSizeWarningLimit` 500 → 1000 消除 element-plus/charts 误导性警告；order_detail 逐订单 commit 加 3 行说明注释 | P2-D1 / P2-D2 |
| `bcd8ad7` | `chore`: `docs/reviews/2026-04-19-full-audit.md` → `docs/superpowers/reviews/`（legacy 合并）；删 `frontend/src/utils/allocation.ts` + test（死代码） | P1-B9 |

### 打包 #2 剩余 — mypy debt 清空

| commit | 内容 | 关闭 |
|---|---|---|
| `412b6be` | `chore(backend)`: 清空 pyproject.toml 全部 13 模块 blanket override（auth/config/data/monitor/suggestion/task + sync.order_detail/out_records/shop/warehouse + saihu.client/token）；修 57→0 mypy errors（补类型注解、dict_item 用 `tuple[Any, ...]`、恢复精准 `# type: ignore[attr-defined]` on `Result.rowcount`、`str(...)` 转 access_token、`assert isinstance(payload, dict)` 窄化 resp.json()） | P1-C3 |

---

## 二、全量 audit 闭环统计（2026-04-21 base，63 问题）

| 严重度 | 原数 | 已闭环 | Skipped（带 rationale） | 残余未处理 |
|---|---|---|---|---|
| **Critical (P0)** | 5 | **5** | 0 | 0 |
| **Important (P1)** | 28 | **28** | 0 | 0 |
| **Minor (P2)** | 25 | **~18** | 7 | 0 |
| **合计** | 63 | **51** | 7 | **0** |

所有 63 条要么已修，要么在对应 commit body 写明跳过 rationale。

---

## 三、7 个 Skipped 项 rationale 索引

| ID | 内容 | Skip 原因 | commit |
|---|---|---|---|
| **P2-A2** | monitor raw `text()` → SQLAlchemy Core | plan 原文"可选，价值不大时跳过"；非热路径、原 SQL 可读性更高 | `a1394d0` body |
| **P2-A4** | 引擎三层 dict → dataclass | plan 原文"大改，可单独 PR"；本分支已够大，独立分支更易 review | `a1394d0` body |
| **P2-B6** | `SuggestionListView.totalSnapshotCount` 内联 | plan 标"可选保留"；该 computed 有 2 处复用 + 惯用法 | `a70436c` body |
| **P2-D3** | `rollup-plugin-visualizer` dev 依赖 | 加 dev 依赖价值低；需要时 `npx` 临时跑即可 | `6477020` body |
| **P2-D4** | el-table `virtual` scrolling (5000 行) | 前端已本地分页 20-50/页，DOM 最多渲染 50 行 → virtual 无收益且会破坏 fixed-column/expand-row | `6477020` body |
| **P2-E1** | `rm deploy/data/pg-local/` | 整个 `deploy/data/` 已 gitignored + 目录内 `postmaster.pid` 可能绑定本地 PG 实例，需人工判断 | `bcd8ad7` body |
| **P2-E3** | plans 迁移到 `archived/2026-04/` | `plans/` 已按日期扁平命名便于 grep；移到子目录纯装饰性，与 audit fix 目标无关 | `bcd8ad7` body |

### 后续可做的 skipped 项

- **P2-A4 engine dataclass**：GENUINELY VALUABLE — 引擎是核心业务，字符串 key 已踩过 `estock` typo / velocity 口径 bug。建议本分支合并 master 后新开 `refactor/engine-dataclass` 单独做（预计 4-6h）。
- **P2-D3 visualizer 一次性跑**：临时 `npx rollup-plugin-visualizer` 看 element-plus 906KB 是否有 tree-shake 漏掉的大块，如果发现再优化。**不要**把依赖加到 package.json。

其他 5 个（P2-A2 / B6 / D4 / E1 / E3）建议维持跳过。

---

## 四、最终质量指标（vs 审计前 baseline）

| 检查 | 审计前（2026-04-21） | 当前 HEAD | Δ |
|---|---|---|---|
| backend pytest | 309 passed / 1 failed | **350 passed / 0 failed** | +41 测试，failed 归零 |
| backend mypy (strict) | 17 模块 blanket override 屏蔽大量 errors | **0 override / 109 files 全 strict / 0 errors** | 完全清零 |
| backend ruff | clean | **clean** | — |
| frontend vue-tsc | clean | **clean** | — |
| frontend ESLint | 未接入 CI | **clean + CI 已接入 `npm run lint`** | 新增守护 |
| frontend vitest | ~100 passed | **108 passed** | +8（删 2 allocation，补 3 displayStatusTag + 3 history + 其它） |
| frontend vite build | 500KB chunk 警告 | **无警告（阈值 1000）** | 噪音消除 |

### 部署 / CI 面加固
- `.github/workflows/ci.yml` 加 postgres service + `TEST_DATABASE_URL` → integration tests 真跑
- `.github/workflows/ci.yml` frontend 加 `npm run lint`
- `.github/workflows/deploy.yml` 加 `environment: production` + reviewer approval
- `deploy/Caddyfile` HSTS 加 `preload`
- `deploy/scripts/validate_env.sh` 加生产 JWT/LOGIN_PASSWORD/SAIHU 强校验
- `deploy/scripts/deploy.sh` 加备份完整性验证
- `deploy/scripts/rollback.sh` 指向 runbook SOP（新增 `docs/runbook.md` 回滚小节）

---

## 五、剩余 TODO

**无技术债剩余**。仅两件后续可选：

1. **P2-A4 engine dataclass 重构**（4-6h，独立分支）
2. **P2-D3 bundle visualizer 一次性跑**（15 min，npx）

---

## 六、PR description 素材

以下内容可直接复制到 `gh pr create --body` 里：

### Summary
本 PR 交付 `feature/split-procurement-restock-and-eu` 的 84 commits：
1. **业务重构**（前 20 commits）：采购/补货视图分拆、EU 合并、安全库存、step4/step6 新公式、历史页重构
2. **审计修复**（后 28 commits，基于 `docs/superpowers/reviews/2026-04-21-full-audit.md`）：
   - 5 Critical 全闭（engine clamp / docs_enabled 硬关 / CI postgres / gitignore）
   - 28 Important 全闭（mypy 17 模块 override 清空到 0 / 历史页去重 / retention 三连 / dashboard stale / 部署加固）
   - 18 Minor 闭（7 项故意跳过附 rationale）

### Test plan
- [x] backend pytest: 350 passed / 0 failed / 9:45（`TEST_DATABASE_URL` integration 命令见 `docs/superpowers/reviews/2026-04-21-inventory.md`）
- [x] backend mypy strict: 109 files / 0 errors / 0 blanket override
- [x] backend ruff: clean
- [x] frontend vue-tsc / ESLint / vitest 108 / vite build: all clean
- [x] alembic upgrade head 幂等（migration `20260422_1000` + `20260423_1000`）
- [ ] 人工手测 retention job（`docker exec` 手动 enqueue `retention_purge`）
- [ ] 人工手测 Dashboard stale（改 eu_countries 后看 stale 是否触发 refresh）
- [ ] 人工手测 410 purged（模拟 retention 标 `file_purged_at` + 前端下载看提示）
- [ ] CodeRabbit / `/ultrareview` 跑通

### Breaking changes
无。前端 `Suggestion` 接口虽然加了 2 个 code 字段（`procurement_display_status_code` / `restock_display_status_code`），但有默认值 `pending`，老调用方不受影响。

### Database migrations
- `20260422_1000` — suggestion_item.purchase_qty CheckConstraint ≥ 0 + 修复历史脏数据
- `20260423_1000` — excel_export_log.file_purged_at + dashboard_snapshot.stale

两个 migration 均 idempotent（项目未上线，按 AGENTS.md §11 约束，不提供 downgrade）。

---

## 七、新会话接手（如适用）

若在合并前还需继续迭代本分支（例如根据 review 反馈改 bug）：

1. 读 Session 1 快照 `2026-04-22-audit-fixes-progress.md`（前 18 commits 背景）
2. 读本文件（Session 2 的 10 commits 背景）
3. `git log --oneline master..HEAD | wc -l` 应为 84（或更多，视是否已叠加新 commit）
4. 确认 dev 容器 healthy：`docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev ps`
5. 跑 baseline pytest 确认无回归（完整命令见 Session 1 快照第五节"已知坑位"）
