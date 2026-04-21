# restock_system 全量 Review 执行策略

> **For agentic workers:** 本文件是 review 策略，不是实施 plan。按 Stage 0 → Stage 1 → Stage 2 → Stage 3 顺序执行。每个 Stage 的交付物都落到 `docs/superpowers/reviews/` 下。

**Goal:** 分阶段对项目做一次体系化 review，覆盖 8 个域（功能完整度 / 核心链路 / 性能 / 技术债 / 垃圾文件 / 部署 / 前端 UX / 死代码），输出可执行的 fix 清单。

**Architecture:** 自动化工具先扫一遍收集事实 → 5 个 subagent 按域并行读代码 → 汇总去重 + 排优先级 → 形成 fix plan 交付。

**Tech Stack:** ruff / mypy / vue-tsc / vitest / pytest / pg_stat + `superpowers:code-reviewer` agent / Explore agent

---

## 先读上下文简报

**新会话开始前先读**：`docs/superpowers/reviews/2026-04-21-session-context.md`

里面写了：
- 当前分支状态（48 commits）
- 本 PR 覆盖的 4 大主题
- 6 个不可逆的架构决策
- 前后端主要文件结构（agent 限 Glob 用）
- 已修复的问题（别重复报告）
- 10 个潜在待 review 的提示点

---

## Stage 0 — 自动化扫描

**目的**：用工具采事实，不烧 agent 上下文。一次人工 15 分钟跑完。

### Task 0.1 — 后端代码质量扫描

- [ ] **Step 1: ruff lint**
```bash
cd backend && ruff check . 2>&1 | tee /tmp/audit-ruff.log
```
Expected: 记录所有 lint warning/error

- [ ] **Step 2: mypy 类型检查（按需）**
```bash
cd backend && mypy app 2>&1 | tee /tmp/audit-mypy.log
```

- [ ] **Step 3: pytest 覆盖率**
```bash
cd backend && python -m pytest --cov=app --cov-report=term-missing 2>&1 | tee /tmp/audit-coverage.log
```

### Task 0.2 — 前端代码质量扫描

- [ ] **Step 1: vue-tsc**
```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | tee /tmp/audit-vue-tsc.log
```

- [ ] **Step 2: ESLint**
```bash
cd frontend && npm run lint 2>&1 | tee /tmp/audit-eslint.log
```

- [ ] **Step 3: vite build（查 bundle 警告）**
```bash
cd frontend && npx vite build 2>&1 | tee /tmp/audit-vite-build.log
```

### Task 0.3 — 垃圾/死代码扫描

- [ ] **Step 1: 未跟踪文件**
```bash
git status --short 2>&1 | tee /tmp/audit-untracked.log
```

- [ ] **Step 2: 工作区大文件**
```bash
find . -size +1M -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/dist/*" 2>&1 | tee /tmp/audit-bigfiles.log
```

- [ ] **Step 3: 前端未使用组件（如安装 ts-prune 可跑）**
```bash
cd frontend && npx ts-prune 2>&1 | tee /tmp/audit-ts-prune.log  # 如果工具没装跳过
```

### Task 0.4 — DB 统计（辅助性能分析）

- [ ] **Step 1: 表行数**
```bash
docker exec restock-dev-db psql -U postgres -d replenish -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;" 2>&1 | tee /tmp/audit-db-tables.log
```

- [ ] **Step 2: 缺索引的慢查询（若启用了 pg_stat_statements）**
```bash
docker exec restock-dev-db psql -U postgres -d replenish -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;" 2>&1 | tee /tmp/audit-slow-queries.log
```

### Task 0.5 — 汇总成 inventory

- [ ] **Step 1: 把所有 /tmp/audit-*.log 汇总成一份结构化文档**
保存到 `docs/superpowers/reviews/2026-04-21-inventory.md`

模板：
```markdown
# 2026-04-21 自动化扫描 inventory

## 后端
- ruff: [count] 个错误，主要类型 ...
- mypy: [count] 个类型错误
- pytest 覆盖率：[%] 
- 未覆盖的关键模块：...

## 前端
- vue-tsc: [count] 个错误
- ESLint: [count] 个 warning
- vite build warnings：chunk X > 500KB ...

## 垃圾/死代码
- 未跟踪文件：[count]
- 大文件（>1M）：...
- 前端 unused exports：[count]

## DB
- 大表 top 5：...
- 慢查询 top 10：...

## Stage 1 agent 输入
每个 agent 起点文件，避免重复扫描：
- Agent A：本清单"后端"部分
- Agent B：本清单"前端"部分
- ...
```

**Stage 0 完成条件**：`docs/superpowers/reviews/2026-04-21-inventory.md` 存在且内容不是占位。

---

## Stage 1 — 5 Subagent 分域审计

### 派发方式

**推荐**：一次 dispatch 5 个 agent（`run_in_background=true` 并发），等所有完成后进 Stage 2。

**agent 类型选择**：
- Agent A/B/C/D 用 `general-purpose` 或 `Explore`
- Agent E 用 `Explore`（范围小）

### Agent A — 后端核心链路 + 后端技术债 + 后端死代码

```
你负责 restock_system 项目的 **后端代码深度审计**。

项目根：E:\Ai_project\restock_system
分支：feature/split-procurement-restock-and-eu

先读：
1. docs/superpowers/reviews/2026-04-21-session-context.md  — 项目背景
2. docs/superpowers/reviews/2026-04-21-inventory.md  — Stage 0 自动化扫描结果

你的范围仅限：
- backend/app/engine/**/*.py
- backend/app/api/**/*.py
- backend/app/models/**/*.py
- backend/app/sync/**/*.py
- backend/app/core/country_mapping.py
- backend/app/core/timezone.py

**不要审计**：tests/、alembic/ 已有迁移、schemas/（前端类型自动对齐无需检查）

你要回答 3 个问题：

### Q1 — 核心链路正确性
- 引擎公式（step3/step4/step6）数学正确吗？
- 边界情况（velocity=0 / 所有国家空 / 单国家 / purchase_qty < 0）处理正确吗？
- EU 映射在 4 个 sync 入口都一致吗？（对照 country_mapping.py）
- can_enable / 翻 OFF / 翻 ON 的事务边界正确吗（有没有 TOCTOU）？

### Q2 — 后端技术债
- 有没有重复代码 / 大文件需要拆？
- 有没有类型隐患（dict[str, Any] 泛滥、缺 TypedDict 的场景）？
- 有没有 raw SQL 字符串拼接的风险？
- 有没有 async 函数里的同步 I/O？

### Q3 — 后端死代码
- 已删字段的残留引用（比如 include_tax / calc_enabled / voided）
- 未使用的 helper 函数
- 覆盖率 = 0 的路径

输出格式（严格遵守）：
### 问题 #N — [一行标题]
- 严重度：Critical / Important / Minor
- 位置：file_path:line
- 现状：[1-2 句说明]
- 建议：[1-2 句修复方向]
- 工作量：S / M / L

所有问题写入：docs/superpowers/reviews/2026-04-21-agent-A-backend.md
```

### Agent B — 前端 UX + 前端死代码

```
你负责 restock_system 项目的 **前端 UX 与死代码审计**。

项目根：E:\Ai_project\restock_system
分支：feature/split-procurement-restock-and-eu

先读：
1. docs/superpowers/reviews/2026-04-21-session-context.md
2. docs/superpowers/reviews/2026-04-21-inventory.md  — 前端部分

你的范围仅限：
- frontend/src/views/**
- frontend/src/components/**
- frontend/src/styles/**
- frontend/src/utils/**
- frontend/src/api/**.ts

**不要审计**：dist/、node_modules/、__tests__/

要回答 2 个问题：

### Q1 — 前端交互/显示
- 响应式布局是否在窄屏破坏？
- Loading / Empty / Error 三态是否齐全？
- hover/focus/disabled 状态是否一致？
- 可访问性（aria、keyboard nav）是否有明显缺漏？
- el-table 的 scroll / 列宽 / 固定列行为是否稳定？
- i18n 文案一致性（同功能是否多处用词不统一？）

### Q2 — 前端死代码
- 未导入的 util / component
- 未用的 props / emits
- 被注释掉的代码块 > 5 行

输出格式和 Agent A 一致。
所有问题写入：docs/superpowers/reviews/2026-04-21-agent-B-frontend.md
```

### Agent C — 功能完整度 + 测试缺口

```
你负责 restock_system 项目的 **功能完整度 review**。

项目根：E:\Ai_project\restock_system
分支：feature/split-procurement-restock-and-eu

先读：
1. docs/superpowers/reviews/2026-04-21-session-context.md
2. AGENTS.md  — 协作规则（关注第 6/9 节）
3. docs/PROGRESS.md  — 已交付能力清单
4. docs/Project_Architecture_Blueprint.md  — 架构蓝图
5. specs/  目录下的 .md  — 所有功能规格

你的范围：对照文档 vs 代码，找出：

### Q1 — 功能缺失
- PROGRESS.md 声称已交付，但代码里没实现或不完整的
- specs/ 里描述了但未实现的
- Blueprint 里的流程缺少的链路

### Q2 — 测试覆盖缺口
- 核心公式 / 关键边界 / 高风险路径的单测或集成测试缺失
- 对照 `backend/tests/` 和 `frontend/src/**/__tests__/` 的覆盖范围

### Q3 — 文档漂移
- AGENTS.md §9 映射表里要求同步但没同步的
- Blueprint 里的 schema / API 描述和当前代码不符的

输出格式同 Agent A。
所有问题写入：docs/superpowers/reviews/2026-04-21-agent-C-completeness.md
```

### Agent D — 性能

```
你负责 restock_system 项目的 **性能瓶颈 review**。

项目根：E:\Ai_project\restock_system
分支：feature/split-procurement-restock-and-eu

先读：
1. docs/superpowers/reviews/2026-04-21-session-context.md
2. docs/superpowers/reviews/2026-04-21-inventory.md  — DB / bundle 数据

你的范围：

### Q1 — 后端性能
- 引擎 step 的算法复杂度（N×M 循环 / 重复查库）
- 高频 API 的 N+1（sync 接口 / dashboard / suggestion list）
- 缺索引的查询（对照 inventory.md 的 DB 统计）
- 事务粒度（有没有长事务锁表）

### Q2 — 前端性能
- bundle chunk 大小超 500KB 的（charts、element-plus）→ 可懒加载？
- 历史页 5000 条全量拉（已改分页，但检查是否还有别的全量拉）
- 大列表渲染是否用 virtual scroll
- 频繁 computed 是否可缓存

### Q3 — DB 性能
- 最大表 top 5 是否有对应业务索引
- JSONB 字段查询是否用 GIN / expression index

输出格式同 Agent A。
所有问题写入：docs/superpowers/reviews/2026-04-21-agent-D-performance.md
```

### Agent E — 部署 + 垃圾文件

```
你负责 restock_system 项目的 **部署能力与仓库整洁度** review。

项目根：E:\Ai_project\restock_system
分支：feature/split-procurement-restock-and-eu

先读：
1. docs/superpowers/reviews/2026-04-21-session-context.md
2. docs/superpowers/reviews/2026-04-21-inventory.md  — 未跟踪/大文件列表
3. docs/deployment.md
4. docs/runbook.md

你的范围：
- deploy/**
- .github/**
- scripts/**
- 仓库根目录（.gitignore / Ai_project.lnk / cloudflared*.exe / tmp 文件）

### Q1 — 部署能力
- Dockerfile / docker-compose 配置安全吗？（secrets 硬编码？root 用户？）
- Caddy 反代规则是否有漏洞（CORS / CSP）
- 健康检查 / 依赖启动顺序是否可靠
- 备份 / 回滚脚本 (deploy/scripts/) 完整性
- CI/CD workflow 触发条件是否过度 / 过漏

### Q2 — 垃圾文件 / 仓库整洁
- 根目录非代码文件（.lnk / .exe / reviews/）该不该 commit
- `docs/superpowers/plans` 里已经实施完的 plan 是否应该归档
- 已废弃的 docker-compose override 文件
- 应该加入 .gitignore 的类型

输出格式同 Agent A。
所有问题写入：docs/superpowers/reviews/2026-04-21-agent-E-deploy.md
```

---

## Stage 2 — 汇总 + 排优先级

### Task 2.1 — 合并 5 份报告

- [ ] **Step 1: 逐份 Read Agent A~E 的报告**
- [ ] **Step 2: 按严重度分桶 + 按文件去重**
- [ ] **Step 3: 用 2D 矩阵排优先级**

优先级规则：
- **P0** (本周)：Critical + 工作量 S/M
- **P1** (2 周)：Important + 工作量 S；或 Critical + 工作量 L
- **P2** (backlog)：Minor 或 Important + 工作量 L
- **P3** (放弃)：主观偏好 / 价值不明确

### Task 2.2 — 输出总报告

- [ ] **Step 1: 写入 `docs/superpowers/reviews/2026-04-21-full-audit.md`**

模板：
```markdown
# 2026-04-21 全量 Review 汇总

## 统计
- Critical: N 条
- Important: N 条
- Minor: N 条

## P0 清单（本周必修）
| # | 问题 | 位置 | 工作量 | 来源 agent |
|---|---|---|---|---|
| 1 | ... | ... | S | A |

## P1 清单（2 周内）
...

## P2 清单（backlog）
...

## 按域分类索引
- 功能完整度：#X, #Y
- 核心链路：...
- 性能：...
- 技术债：...
- 死代码：...
- 部署：...
- 前端 UX：...
- 垃圾文件：...
```

---

## Stage 3 — 形成 fix plan

### Task 3.1 — 按优先级生成 plan

- [ ] **Step 1: 用户拍板要做 P0 / P0+P1 / 全部**
- [ ] **Step 2: 把选定项展开为 commit 级 task**
- [ ] **Step 3: 写入 `docs/superpowers/plans/2026-04-22-audit-fixes.md`**

格式参考本仓库已有的 plan 文档（如 `2026-04-20-split-procurement-restock-and-eu-mapping.md`）。

### Task 3.2 — 执行 fix

按 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 推进。

---

## 执行 check list

- [ ] Stage 0.1 - 0.5 自动化扫描 + inventory 写入
- [ ] Stage 1 — 5 agent 并行 dispatch，5 份报告落地
- [ ] Stage 2 — 合并去重 + full-audit.md 落地
- [ ] Stage 3 — fix plan 落地 + 用户审阅 + 开执行
