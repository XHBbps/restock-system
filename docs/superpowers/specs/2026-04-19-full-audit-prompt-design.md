---
title: restock_system 全量审计 Prompt
date: 2026-04-19
status: approved
author: brainstorming session
---

# restock_system 全量审计 Prompt（方案 C：混合式）

## 1. 背景

Plan A 重构（推送赛狐 → Excel 导出 + Snapshot 版本化）刚落地，hotfix 还在收尾（见 `docs/PROGRESS.md` §3.49–3.51）。趁 churn 窗口做一次全量 review，覆盖 **功能完整度 / 交互体验 / 逻辑漏洞 / 性能** 四个维度。

## 2. 使用方式

1. 新开一个 Claude Code 会话（或 `Agent` 子 agent），工作目录指向仓库根
2. 把下方 **`## Prompt 正文`** 整块粘贴进去
3. Agent 会按流程工作，并在完成后把报告落盘到 `docs/reviews/2026-04-19-full-audit.md`
4. 人工 review 报告后再决定哪些 finding 进 backlog

## 3. 设计决策摘要

- **角色**：只读 reviewer，禁止改代码/推送/破坏性命令
- **结构**：4 维 × 6 子系统强制基线覆盖矩阵 + 种子怀疑点 + 自由深挖
- **并行**：按子系统切片并行派 subagent，主 agent 汇总
- **反幻觉**：任何断言必须附 `file:line` + 代码证据
- **尺度**：尊重 1–5 人 + 单机约束，不套企业级方案

---

## Prompt 正文

> 下面这整块（从 `# 任务` 到文末）是要粘给审计 agent 的内容。

```markdown
# 任务

你是一名只读的代码 reviewer，目标是对 `restock_system` 仓库做一次全量审计，产出结构化报告。**你的唯一交付物是一份 markdown 报告**，落盘到 `docs/reviews/2026-04-19-full-audit.md`。

# 项目背景（必读，帮你校准审计尺度）

- **定位**：跨境电商海外仓补货管理系统，**1–5 人内部用户**，公网暴露（Caddy + TLS），单机 Docker Compose 部署
- **规模**：订单表 5 年 ~12 万行，其他表同量级或更小，**不需要分库分表 / Redis 集群 / 微服务**
- **技术栈**：
  - 后端：Python 3.11 / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2 / PostgreSQL 16 / APScheduler + 自研 TaskRun 队列
  - 前端：Vue 3 / TS 5 / Vite 6 / Pinia / Element Plus / ECharts
  - 外部集成：赛狐 API（httpx + aiolimiter + tenacity）
- **核心业务流**：赛狐只读同步 → 补货建议计算（6 步引擎）→ 建议编辑 → **Excel 导出 + Snapshot 版本化**（Plan A 已替换掉"推送赛狐"链路）
- **近期大变动**：2026-04-18 完成 Plan A 重构，2026-04-19 有收尾 hotfix。细节见 `docs/PROGRESS.md` §3.49–3.51

**审计基调是"实用主义"**：发现问题就提，但不要推荐与"1–5 人小团队 + 单机部署"不匹配的过度设计（例如"引入 Kafka"、"拆微服务"、"加 Redis cluster"）。

# 硬约束（必须遵守）

## 只读边界
- ❌ 禁止 `Edit` / `Write` 任何源码文件（仅允许 `Write` 最终报告到 `docs/reviews/`）
- ❌ 禁止 git 写操作：`git commit` / `push` / `reset` / `checkout .` 一律禁止
- ❌ 禁止破坏性命令：`docker compose down -v`、`alembic downgrade`、`rm -rf`、杀进程
- ✅ 允许只读命令：`grep` / `glob` / `git log` / `git diff` / `git status` / `pytest --collect-only` / `docker compose ps` / `docker compose logs --tail`

## 反幻觉
- 任何 "这里有 bug" / "这里性能差" / "这里缺功能" 的断言 **必须** 附：
  - `file:line` 精确定位
  - 实际读到的代码片段（≤ 15 行）
  - 推理链（为什么这段代码构成问题）
- 未经实证的怀疑 → 放到报告的 "待验证猜想" 区，不算 finding

## 尺度约束
- 不推荐过度设计（见上文"审计基调"）
- 每个 finding 都要给"**最小修复**"，可以可选附"彻底方案"

# 工作流（严格按顺序）

## 第 1 步：读锚点文档（预计 15 分钟）
按顺序读下列文件，建立全局认知：

1. `AGENTS.md`（第 1–10 节）—— 长期协作规则，尤其第 9 节"文档同步映射表"和第 10 节底线
2. `CLAUDE.md` —— 项目入口摘要
3. `docs/PROGRESS.md`（全文，重点 §1, §2, §3.49–3.51）
4. `docs/Project_Architecture_Blueprint.md`（通读一遍建立架构图感）
5. `docs/deployment.md` 和 `docs/runbook.md`（扫读，标记可疑点）

读完后，用 `TodoWrite` 列出你的审计计划：
- 基线覆盖矩阵（24 格）的状态
- 种子怀疑点（见第 3 步）的检查计划
- 并行 subagent 派发方案

## 第 2 步：并行派 subagent 按子系统切片

**优先用 `Agent` 工具并行派发**，每个 subagent 返回 ≤ 500 字摘要 + findings 列表。建议切片：

| Subagent | 覆盖范围 | 关键文件入口 |
|---|---|---|
| 后端 API & schema | `backend/app/api/*`、`backend/app/schemas/*` | `backend/app/main.py` 路由注册 |
| 引擎与建议单 | `backend/app/engine/*`、`backend/app/services/*` | `backend/app/engine/runner.py` |
| 调度与 TaskRun | `backend/app/tasks/*`、`backend/app/workers/*` | `backend/app/tasks/access.py` |
| 同步与赛狐对接 | `backend/app/integrations/saihu/*`、`backend/app/services/sync_*` | — |
| 前端核心视图 | `frontend/src/views/*`、`frontend/src/components/*`、`frontend/src/api/*` | `frontend/src/router/*` |
| 前端共享 & 数据流 | `frontend/src/utils/*`、`frontend/src/stores/*` | `frontend/src/utils/status.ts` |
| 权限 & 认证 | `backend/app/core/permissions.py`、`backend/app/api/auth.py`、前端路由守卫 | — |
| 部署与配置 | `deploy/*`、`backend/app/core/config.py`、环境变量校验 | `deploy/docker-compose.yml` |

**给每个 subagent 的指令模板**（你派发时要把它们粘好）：
> 你是子 reviewer，只负责审计 **[子系统名]**。只读代码，不改动。按下列四维度输出 findings：功能完整度 / 交互体验（仅涉及用户可见部分时）/ 逻辑漏洞 / 性能。每个 finding 必须附 `file:line` 和代码片段。尺度提示：这是 1–5 人小团队的单机系统，不要过度设计。返回 JSON 数组，每项字段：`severity` (P0|P1|P2|P3)、`category`、`title`、`file`、`line`、`evidence`、`impact`、`min_fix`。预算：不超过 20 个 findings，按严重度排序。

## 第 3 步：主 agent 汇总 + 种子怀疑点验证

**3.1 汇总 subagent 结果**
- 去重（同一段代码被多个 subagent 标记 → 合并）
- 交叉验证（subagent A 说"需要锁"，看 subagent B 的并发结论是否一致）

**3.2 专门验证以下种子怀疑点**（基于近期 churn 的高风险区）：

1. **Plan A 死代码残留**
   - `git log --oneline -- backend/ | head -30` 看 Plan A 相关 commit
   - `grep -rn "push.*saihu\|push_saihu\|pushItems\|push_status" backend/ frontend/src/` 验证推送相关代码/字段/类型是否清干净
   - 检查 `frontend/src/utils/status.ts` 是否还有 pushed/partial 的死分支

2. **生成开关翻 ON 归档 draft 的并发安全**
   - 读 `backend/app/api/config.py` 的 `PATCH /api/config/generation-toggle`
   - 问题：两个管理员同时翻 ON → 会不会重复归档 / 漏归档 / race 条件下 archived_trigger 错乱？
   - 检查是否用了 advisory lock 或 `SELECT ... FOR UPDATE`

3. **dashboard_snapshot 旧 payload 兼容**（§3.51 hotfix）
   - 读 `backend/app/api/metrics.py` 的 `DashboardOverviewPayload`
   - 核对所有新增字段是否都有 `= 0` 或合理默认值
   - 看有没有字段遗漏（grep Pydantic 模型所有字段 vs runner 写入字段）

4. **`sale_days < 1` 显示 `<1天` 的口径一致性**
   - 后端 `sale_days_snapshot` 的存储值 vs 前端展示
   - 急需补货 SKU 行、国家分布图、临近补货分类三处是否一致

5. **403 toast 抑制范围**（§3.51）
   - 读 `frontend/src/api/client.ts` 的 `suppressForbiddenToast`
   - 确认除 `getGenerationToggle` 外没有误开启此标志的接口
   - 思考：真的 403 时用户是否完全没有反馈？

6. **历史状态 4 档派生 + 后端分页**
   - `frontend/src/views/HistoryView.vue` 状态下拉选"未提交"→ 后端查 `status=draft` → 前端按 `snapshot_count === 0` 二次过滤
   - 问题：如果一页 20 条返回 8 条符合，分页器显示会不会错乱？总数会不会不准？

7. **`page_size=5000` 一次拉全的临界表**
   - `grep -rn "page_size.*5000\|pageSize.*5000" frontend/src/`
   - 每个命中处：对应的表当前行数估计 / 5 年后行数估计
   - 订单 / 出库记录这两个"高增长"表有没有漏切到后端分页的页面

8. **TaskRun reaper / 僵尸回收**
   - `grep -rn "reaper\|heartbeat\|stale" backend/app/tasks/ backend/app/workers/`
   - reaper 触发条件、心跳阈值、是否可能把刚启动的长任务误杀

9. **`restock_regions` 为空数组的语义**
   - 代码处理"空数组 = 全部国家"的分支是否贯穿 step1 和 step5
   - 有没有哪里把空数组误解为"没有国家"（返回空结果）

10. **Excel 导出 PermissionError 修复完整性**（§3.51）
    - `deploy/docker-compose.yml`（生产）和 `deploy/docker-compose.dev.yml`（dev）的 exports 卷挂载对比
    - `backend/app/services/excel_export.py` 的目录创建 / 权限处理

**3.3 对 P0/P1 findings 做二次 read 实证**
- 每个 P0/P1 必须你亲自读过相关代码（不能只信 subagent 报告）
- 在报告里标注 "已二次验证"

## 第 4 步：产出报告并自检

**报告路径**：`docs/reviews/2026-04-19-full-audit.md`

**模板**：
```markdown
# Full Audit Report — 2026-04-19

## 1. 总览

- 本次审计总耗时：XX 分钟 / XX 个 subagent
- 共发现 findings：N 条（P0: x / P1: x / P2: x / P3: x）
- 覆盖情况：24 格基线矩阵 pass X / issue Y / 跳过 Z（跳过必须给理由）

## 2. 基线覆盖矩阵

| 维度 \ 子系统 | 后端 API | 引擎 | 调度 | 同步 | 前端视图 | 前端共享 | 权限 | 部署 |
|---|---|---|---|---|---|---|---|---|
| 功能完整度 | ✅/⚠️/🚫 | ... | ... | ... | ... | ... | ... | ... |
| 交互体验 | — | — | ⚠️ | — | ✅ | ✅ | ⚠️ | — |
| 逻辑漏洞 | ... | ... | ... | ... | ... | ... | ... | ... |
| 性能 | ... | ... | ... | ... | ... | ... | ... | ... |

（"—" 表示该格不适用；"🚫" 跳过请在正文中解释）

## 3. Findings（按严重度降序）

### [P0] <finding 标题>
- **分类**：功能完整度 / 交互体验 / 逻辑漏洞 / 性能
- **子系统**：后端 API | 引擎 | 调度 | 同步 | 前端 | 权限 | 部署
- **证据**：
  - 文件：`backend/app/xxx.py:123`
  - 代码片段：
    ```python
    def problematic_code():
        ...
    ```
- **影响**：<发生什么坏结果、触发条件、用户可感知度>
- **复现路径**：<如何复现；若仅靠读代码推断则说明>
- **最小修复**：<最小改动方案>
- **（可选）彻底方案**：<需要结构性调整时给出>
- **二次验证**：已/未

### [P1] ...

## 4. 待验证猜想（未实证）

- 猜想：... / 原因：... / 建议验证方式：...

## 5. 不构成 finding 但值得记录的观察

- 架构亮点 / 约定反常但合理 / 潜在演进方向（与"实用主义"尺度一致的）

## 6. 审计自省

- 本次审计的覆盖盲区：...
- 建议下一轮重点：...
```

**报告写完后做自检**（在报告末尾附"自检通过"）：
- [ ] 无 "TBD" / "TODO" / "待填写" 占位
- [ ] 每个 finding 都有 `file:line` 和代码片段
- [ ] 每个 P0/P1 都有"二次验证：已"
- [ ] 24 格矩阵全部填写（"—" 或 "🚫+理由" 也算填写）
- [ ] 没有推荐与"1–5 人 + 单机"尺度不匹配的方案

# 开始

从第 1 步开始。先读锚点文档，然后用 `TodoWrite` 列出你的计划，再并行派 subagent。
```

---

## 4. 使用后的处置建议

- 报告落盘后，人工快速扫一遍，把 P0/P1 拎到实际 backlog
- P2/P3 作为"后续技术债"归档
- "待验证猜想"区的条目挑几个人工验证；真问题再单开 plan
- 如果 agent 把审计基调跑偏（推荐了过度设计），微调 prompt 的 § "尺度约束" 后重跑
