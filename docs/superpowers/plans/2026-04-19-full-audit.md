# restock_system 全量审计执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans 或 superpowers:subagent-driven-development 按任务逐步执行。每个步骤带 `- [ ]` 复选框。
>
> **注意**：本计划是**只读审计**，不是常规开发任务。没有 TDD 循环；每个 Task 的"完成判据"是"产出可核对的中间件产物"（subagent 摘要、种子验证报告、最终 markdown 报告）。

**Goal**：按 approved spec（`docs/superpowers/specs/2026-04-19-full-audit-prompt-design.md`）落地一次全量代码审计，输出结构化报告到 `docs/reviews/2026-04-19-full-audit.md`。

**Architecture**：主 agent 编排 → 用 `Agent` 工具并行派发 8 个 `Explore` 类型 subagent 做子系统切片 → 主 agent 汇总、去重、交叉验证 → 系统性验证 10 个种子怀疑点（用 systematic-debugging skill 纪律）→ 落盘报告 + 自检（verification-before-completion）。全程只读，禁止 `Edit` / `Write` 源码、禁止 git 写操作。

**Tech Stack**：Read / Grep / Glob / Bash（只读命令） + Agent(subagent_type=Explore) + Skills：`dispatching-parallel-agents`、`systematic-debugging`、`verification-before-completion`。

**硬约束（摘自 spec §硬约束，必须遵守）**：
- ❌ 禁止 `Edit` / `Write` 任何源码文件（仅允许 `Write` 最终报告到 `docs/reviews/`）
- ❌ 禁止 git 写操作
- ❌ 禁止破坏性命令（`docker compose down -v`、`alembic downgrade`、`rm -rf`、杀进程）
- ✅ 允许只读命令：`grep` / `glob` / `git log` / `git diff` / `git status` / `pytest --collect-only` / `docker compose ps` / `docker compose logs --tail`
- 反幻觉：任何断言必须附 `file:line` + 代码片段（≤15 行）+ 推理链

---

## Task 1：读锚点文档 + 建立审计上下文

**目标**：主 agent 亲自建立项目认知，不依赖 subagent 信息，保证后续汇总有能力交叉验证。

**Files**：
- Read: `AGENTS.md`
- Read: `CLAUDE.md`
- Read: `docs/PROGRESS.md`（重点 §1, §2, §3.49–3.51）
- Read: `docs/Project_Architecture_Blueprint.md`
- Read: `docs/deployment.md`（扫读）
- Read: `docs/runbook.md`（扫读）

- [ ] **Step 1.1：读 AGENTS.md 第 1–10 节**
  Run: `Read file_path="E:\Ai_project\restock_system\AGENTS.md"`
  记下：第 9 节文档同步映射表、第 10 节不可违反的底线。

- [ ] **Step 1.2：读 CLAUDE.md**
  Run: `Read file_path="E:\Ai_project\restock_system\CLAUDE.md"`

- [ ] **Step 1.3：读 PROGRESS.md**
  大文件（>25k tokens），分段读：先 offset=0 limit=800 看 §1 §2，再定位 §3.49–3.51 的行号详读。
  Run: `Read file_path="E:\Ai_project\restock_system\docs\PROGRESS.md" offset=0 limit=800`

- [ ] **Step 1.4：读架构蓝图**
  Run: `Read file_path="E:\Ai_project\restock_system\docs\Project_Architecture_Blueprint.md"`
  建立"6 步引擎 + TaskRun 队列 + 赛狐集成层 + Plan A 导出"的组件图心智。

- [ ] **Step 1.5：扫读 deployment.md 和 runbook.md**
  Run: `Read file_path="E:\Ai_project\restock_system\docs\deployment.md"`
  Run: `Read file_path="E:\Ai_project\restock_system\docs\runbook.md"`
  记下可疑点（比如健康检查、环境变量、exports 卷挂载等）。

- [ ] **Step 1.6：用 git log 快速看近一周 commit**
  Run: `git log --oneline --since="7 days ago"`
  确认 Plan A 相关 commit hash 列表，供 Task 3 的"死代码残留"种子点使用。

- [ ] **Step 1.7：用 TodoWrite 列出审计计划**
  已通过 `TaskCreate` 建立 5 个顶层任务，Task 1 为 in_progress。Task 1 结束时标记 completed 并开启 Task 2。

**完成判据**：主 agent 能用一两句话概括每个子系统边界、能说出 §3.49–3.51 修了哪些问题、知道 Plan A commit 范围。

---

## Task 2：并行派发 8 个 subagent 做子系统切片

**目标**：把审计工作量分摊给子 agent，主 agent 窗口只保留 ≤500 字摘要 + finding 列表。**必须同一条消息里发出 8 个 Agent 调用并行跑**（dispatching-parallel-agents skill 要求）。

**Files（每个 subagent 的 scope）**：

| # | 子系统 | Scope 文件范围 | Entry 文件 |
|---|---|---|---|
| A | 后端 API & schema | `backend/app/api/*`、`backend/app/schemas/*` | `backend/app/main.py` |
| B | 引擎与建议单 | `backend/app/engine/*`、`backend/app/services/suggestion*` | `backend/app/engine/runner.py` |
| C | 调度与 TaskRun | `backend/app/tasks/*`、`backend/app/workers/*` | `backend/app/tasks/access.py` |
| D | 同步与赛狐对接 | `backend/app/integrations/saihu/*`、`backend/app/services/sync_*` | - |
| E | 前端核心视图 | `frontend/src/views/*`、`frontend/src/components/*`、`frontend/src/api/*` | `frontend/src/router/*` |
| F | 前端共享 & 数据流 | `frontend/src/utils/*`、`frontend/src/stores/*` | `frontend/src/utils/status.ts` |
| G | 权限 & 认证 | `backend/app/core/permissions.py`、`backend/app/api/auth.py`、前端路由守卫 | - |
| H | 部署与配置 | `deploy/*`、`backend/app/core/config.py`、环境变量校验 | `deploy/docker-compose.yml` |

- [ ] **Step 2.1：同一条消息里发出 8 个 Agent 调用**
  关键点：**一条 assistant 消息内 8 个 `<invoke name="Agent">` 块**，才能真正并行。每个 subagent 用下面的 prompt 模板（把 `{SCOPE_NAME}`、`{SCOPE_PATHS}`、`{ENTRY}` 替换掉）：

  ```
  description: "审计 {SCOPE_NAME}"
  subagent_type: "Explore"
  prompt: |
    你是 restock_system 仓库的只读子 reviewer，只负责审计以下子系统：

    子系统：{SCOPE_NAME}
    Scope 路径：{SCOPE_PATHS}
    推荐入口：{ENTRY}

    # 项目背景（校准审计尺度）
    - 跨境电商海外仓补货系统，1–5 人内部用户，公网暴露（Caddy+TLS），单机 Docker Compose
    - 订单表 5 年 ~12 万行；不需要分库分表/Redis 集群/微服务
    - 后端：Python 3.11 / FastAPI / SQLAlchemy 2.0 async / PostgreSQL 16 / APScheduler+自研 TaskRun
    - 前端：Vue 3 / TS 5 / Vite 6 / Pinia / Element Plus / ECharts
    - 核心业务流：赛狐只读同步 → 6 步引擎 → Excel 导出 + Snapshot 版本化（Plan A 已替换"推送赛狐"）
    - 近期大变动：2026-04-18 Plan A 重构落地，2026-04-19 §3.49–3.51 收尾 hotfix

    # 硬约束
    - 只读：禁止 Edit/Write 任何文件、禁止 git 写、禁止破坏性命令
    - 反幻觉：每个 finding 必须附 file:line、代码片段（≤15 行）、推理链
    - 尺度：这是 1–5 人小团队单机系统，**不要推荐过度设计**（禁止建议 Kafka/微服务/Redis cluster 等）

    # 输出格式（严格 JSON 数组，最多 20 条，按 severity 降序）
    每项字段：
    - severity: "P0" | "P1" | "P2" | "P3"
    - category: "功能完整度" | "交互体验" | "逻辑漏洞" | "性能"
    - title: 简短标题
    - file: "backend/app/xxx.py"
    - line: 行号（int）
    - evidence: 代码片段（≤15 行 markdown code block）
    - impact: 发生什么坏结果、触发条件、用户可感知度
    - min_fix: 最小修复描述
    - reasoning: 为什么这段代码构成问题（1-3 句）

    JSON 之外，再用 ≤500 字中文摘要概括本子系统整体健康度和你最担心的 top 3 问题。

    按四维度自查覆盖：功能完整度 / 交互体验（仅涉及用户可见部分时）/ 逻辑漏洞 / 性能。

    开始。
  ```

- [ ] **Step 2.2：等 8 个 subagent 全部返回**
  返回后做一次基本合法性检查：JSON 是否能解析、是否都有 file/line、是否没有跑出 scope。

- [ ] **Step 2.3：汇总到主 agent 的工作笔记**
  在 TodoList 里或消息里维护一张"汇总表"：{subsystem, finding_id, severity, title, file:line}。暂不写入最终报告。

**完成判据**：8 个 subagent 都返回了有效 JSON + 摘要；主 agent 有一张按子系统分组的 finding 总表。

---

## Task 3：汇总 + 10 个种子怀疑点系统验证

**目标**：
1. 去重、交叉验证 subagent 结果
2. 用 `systematic-debugging` skill 的纪律，**主 agent 亲自**验证 spec §3.2 列的 10 个种子怀疑点（不能只信 subagent）

- [ ] **Step 3.1：去重**
  同一段代码被多个 subagent 标为 finding → 合并，保留最详尽的一条并把其他 subagent 的补充证据附上。

- [ ] **Step 3.2：交叉验证**
  若 subagent A 说"这里需要加锁"，看 subagent B/C 对同一代码路径的结论是否一致；冲突时主 agent 读一次源码定夺。

- [ ] **Step 3.3：种子点 1 — Plan A 死代码残留**
  ```bash
  git log --oneline -- backend/ | head -30
  ```
  Run Grep: pattern=`push.*saihu|push_saihu|pushItems|push_status`, path=`backend/` and `frontend/src/`
  Read: `frontend/src/utils/status.ts`
  判断：是否还有 pushed/partial 死分支、PushStatus 枚举残留、后端 push_* 函数未删。

- [ ] **Step 3.4：种子点 2 — 生成开关翻 ON 归档 draft 的并发安全**
  Read: `backend/app/api/config.py`（找 `PATCH /api/config/generation-toggle`）
  检查：是否使用 `pg_advisory_xact_lock` 或 `SELECT ... FOR UPDATE`；两个管理员同时翻 ON 的 race。

- [ ] **Step 3.5：种子点 3 — dashboard_snapshot 旧 payload 兼容**
  Read: `backend/app/api/metrics.py`（定位 `DashboardOverviewPayload`）
  Grep: Pydantic 模型所有字段 vs `backend/app/engine/runner.py` 写入字段，核对新增字段是否都有 `= 0` 或合理默认值。

- [ ] **Step 3.6：种子点 4 — `sale_days < 1` 显示 `<1天` 口径一致性**
  Grep: `sale_days`、`sale_days_snapshot`、`<1天` on both backend and frontend
  核对：后端存储值 vs 前端展示（急需补货 SKU 行 / 国家分布图 / 临近补货分类）。

- [ ] **Step 3.7：种子点 5 — 403 toast 抑制范围**
  Read: `frontend/src/api/client.ts`（找 `suppressForbiddenToast`）
  Grep: `suppressForbiddenToast` 所有调用点
  判断：是否除 `getGenerationToggle` 外被误用；真 403 时用户是否完全没有反馈。

- [ ] **Step 3.8：种子点 6 — 历史状态 4 档派生 + 后端分页**
  Read: `frontend/src/views/HistoryView.vue`
  判断：后端查 `status=draft` → 前端按 `snapshot_count === 0` 二次过滤；分页器在一页 20 条返回 8 条符合时是否错乱、总数是否失准。

- [ ] **Step 3.9：种子点 7 — `page_size=5000` 临界表**
  Grep: `page_size.*5000|pageSize.*5000` in `frontend/src/`
  对每个命中处估计当前行数和 5 年后行数；标记订单 / 出库记录是否漏切后端分页。

- [ ] **Step 3.10：种子点 8 — TaskRun reaper / 僵尸回收**
  Grep: `reaper|heartbeat|stale` in `backend/app/tasks/` `backend/app/workers/`
  判断：reaper 触发条件、心跳阈值、是否可能把刚启动的长任务误杀。

- [ ] **Step 3.11：种子点 9 — `restock_regions` 空数组语义**
  Grep: `restock_regions` 在 `backend/app/engine/`（重点 step1 和 step5）
  判断："空数组=全部国家"的分支是否贯穿；有无地方误解为"没有国家"。

- [ ] **Step 3.12：种子点 10 — Excel 导出 PermissionError 修复完整性**
  Read: `deploy/docker-compose.yml`（生产）
  Read: `deploy/docker-compose.dev.yml`（dev）
  Read: `backend/app/services/excel_export.py`
  对比 exports 卷挂载 + 目录创建 + 权限处理。

- [ ] **Step 3.13：P0/P1 findings 二次 read 实证**
  对所有 severity=P0|P1 的 finding（不论来源），主 agent 亲自 Read 对应文件 ±20 行上下文，确认描述准确。在每条 finding 上加标记 `二次验证：已`。

**完成判据**：10 个种子点每个都有"已验证"或"已确认为非问题"结论；所有 P0/P1 finding 都有二次验证标记。

---

## Task 4：产出报告 + 自检

**目标**：按 spec §第 4 步模板落盘最终 markdown 报告。

**Files**：
- Create: `docs/reviews/2026-04-19-full-audit.md`

- [ ] **Step 4.1：按模板生成报告内容**
  严格用 spec §第 4 步提供的模板骨架：
  ```
  # Full Audit Report — 2026-04-19

  ## 1. 总览
  - 耗时 / subagent 数 / finding 总数（P0/P1/P2/P3 分布）
  - 24 格基线矩阵 pass/issue/跳过 统计

  ## 2. 基线覆盖矩阵
  | 维度 \ 子系统 | 后端 API | 引擎 | 调度 | 同步 | 前端视图 | 前端共享 | 权限 | 部署 |
  |---|---|---|---|---|---|---|---|---|
  | 功能完整度 | ... | ... | ... | ... | ... | ... | ... | ... |
  | 交互体验 | — | — | ⚠️ | — | ✅ | ✅ | ⚠️ | — |
  | 逻辑漏洞 | ... | ... | ... | ... | ... | ... | ... | ... |
  | 性能 | ... | ... | ... | ... | ... | ... | ... | ... |

  ## 3. Findings（按 severity 降序）
  ### [P0] <标题>
  - 分类 / 子系统 / 证据（file:line + 代码片段） / 影响 / 复现 / 最小修复 / （可选）彻底方案 / 二次验证：已

  ### [P1] ...
  ### [P2] ...
  ### [P3] ...

  ## 4. 待验证猜想（未实证）
  ## 5. 不构成 finding 但值得记录的观察
  ## 6. 审计自省

  ## 7. 自检
  [x] 无 TBD/TODO/待填写
  [x] 每个 finding 都有 file:line + 代码片段
  [x] 每个 P0/P1 都有"二次验证：已"
  [x] 24 格矩阵全部填写
  [x] 没有推荐与"1–5 人 + 单机"尺度不匹配的方案

  自检通过 ✅
  ```

- [ ] **Step 4.2：Write 报告**
  Run: `Write file_path="E:\Ai_project\restock_system\docs\reviews\2026-04-19-full-audit.md" content=<完整报告 markdown>`
  注：`docs/reviews/` 目录不存在时 `Write` 会自动创建父目录。

- [ ] **Step 4.3：用 verification-before-completion skill 做最后自检**
  逐项核对：
  - 所有 finding 是否有 `file:line` + 代码片段
  - P0/P1 是否全部"二次验证：已"
  - 矩阵是否 24 格都填了（`—` 或 `🚫+理由` 也算填）
  - 是否有推荐 Kafka / 微服务 / Redis cluster 等过度设计（必须删除）
  - 文件路径用反引号包裹、行号正确

- [ ] **Step 4.4：不 commit**
  按硬约束，审计 agent 禁止 git 写操作。报告落盘后，主 agent 告知用户"报告已生成在 `docs/reviews/2026-04-19-full-audit.md`，人工审阅后再决定是否 commit 和分流 backlog"。

**完成判据**：报告文件存在、自检全部 ✅、未触发任何 git 写操作。

---

## 不在本计划范围（spec §4 "使用后的处置"）

以下动作由**人工**在审计结束后决定，本计划不执行：
- 把 P0/P1 拎到实际 backlog
- P2/P3 归档为技术债
- 对"待验证猜想"区条目单开 plan
- 如果尺度跑偏，微调 spec 的"尺度约束"后重跑

---

## 自检（写完计划后做）

- [x] **Spec 覆盖**：spec 的 4 个工作流步骤全部映射到 Task 1-4；10 个种子点全部对应 Step 3.3-3.12；报告模板对应 Step 4.1。
- [x] **占位符扫描**：所有 Step 都有具体命令 / 文件路径 / 判据，无 "TBD"。
- [x] **类型一致**：Task 之间引用的 `subagent_type=Explore`、`Agent` 工具、`docs/reviews/2026-04-19-full-audit.md` 路径各处统一。
- [x] **硬约束复述**：计划顶部和 Task 4.4 都强调了只读约束。
