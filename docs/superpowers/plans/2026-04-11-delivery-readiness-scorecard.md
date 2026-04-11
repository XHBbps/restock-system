# Delivery Readiness Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the delivery readiness scoring exercise defined in `docs/superpowers/specs/2026-04-11-delivery-readiness-scorecard-design.md`, producing per-module checkpoint files, a calibration record, and a final consolidated report with action items.

**Architecture:** Audit-style execution (not code implementation). Phase 0 sets up directories. Phase 1 audits 8 modules sequentially with user confirmation at each checkpoint. Phase 2 aggregates scores into the final report. Each module audit reads code, applies the 5-level Rubric, scores 9 dimensions (or marks N/A), and produces a markdown file with evidence references.

**Tech Stack:** Read/Grep/Bash (pytest, vue-tsc) for evidence gathering. Markdown for all deliverables. Git for committing each封板 module file.

---

## Reference Documents (read once before starting)

- **Spec** (authoritative source): `docs/superpowers/specs/2026-04-11-delivery-readiness-scorecard-design.md`
  - Section 2: 9 维度的 5 级 Rubric（每次打分必须对照）
  - Section 3: 8 模块的范围与适用矩阵
  - Section 4: 4 汇总组权重与计算公式
  - Section 6: P0/P1 候选清单（每个模块审计时必须交叉引用）
- **Project context**: `AGENTS.md`, `docs/PROGRESS.md`, `docs/Project_Architecture_Blueprint.md`

---

## Phase 0: Setup

### Task 0: 创建评分卡工作目录

**Files:**
- Create: `docs/superpowers/scorecard/_calibration.md`
- Create: `docs/superpowers/scorecard/.gitkeep`

- [ ] **Step 1: 创建目录与占位文件**

```bash
mkdir -p docs/superpowers/scorecard
```

- [ ] **Step 2: 写入 _calibration.md 初始内容**

Write to `docs/superpowers/scorecard/_calibration.md`:

```markdown
# 评分标尺一致性记录

> 用途：每完成一个模块的评分后，记录每个维度的具体打分理由和判据匹配，
> 确保后续模块的同一维度评分与本记录一致。

> 更新规则：每个模块的 checkpoint 完成且用户确认后，由 Claude 追加该模块的标尺记录。

---

## D1 功能完整性

（待 M1 完成后填入第一条标尺）

## D2 代码质量

（待填入）

## D3 安全性

（待填入）

## D4 可部署性

（待填入）

## D5 可观测性

（待填入）

## D6 可靠性

（待填入）

## D7 可维护性

（待填入）

## D8 性能与容量

（待填入）

## D9 用户体验

（待填入）
```

- [ ] **Step 3: 提交目录初始化**

```bash
git add docs/superpowers/scorecard/_calibration.md docs/superpowers/plans/2026-04-11-delivery-readiness-scorecard.md
git commit -m "docs(superpowers): 初始化云交付评分卡执行目录与计划"
```

---

## Phase 1: 模块逐项审计（8 个 checkpoint）

### 通用执行说明（每个 M1-M8 任务都遵循）

每个模块任务严格按以下子步骤执行：

1. **证据采集**：阅读"证据路径"列出的所有文件，运行必要的验证命令（pytest/grep）
2. **维度打分**：对照 spec 第 2 节的 5 级 Rubric，给每个适用维度打 0-4 分（N/A 维度直接标 N/A）
3. **交叉引用 P0/P1 候选**：spec 第 6 节列出的候选项中，凡是属于本模块的，必须在打分时给出"已实现/部分实现/未实现"的判定
4. **写入 checkpoint 文件**：按 spec 第 5.2 节的模板写入 `docs/superpowers/scorecard/M{n}-{name}.md`
5. **更新标尺记录**：把本模块每个维度的打分理由追加到 `_calibration.md`
6. **用户确认**：以摘要形式呈现给用户，等待 ✅/🔧 反馈
7. **封板 + commit**：用户确认后 commit 该模块的 checkpoint 文件 + 更新后的 calibration

**Rubric 速查（每次打分都对照）**：
- 0 缺失 / 1 初级 / 2 可用 / 3 良好 / 4 优秀
- 累积式：3 = 2 + 额外项
- 完整判据见 spec 第 2 节

---

### Task 1: M1 赛狐集成 审计

**Files:**
- Read: `backend/app/saihu/client.py`、`backend/app/saihu/token.py`、`backend/app/saihu/rate_limit.py`、`backend/app/saihu/endpoints/*.py`
- Read: `backend/app/sync/*.py`（所有 sync job）
- Read: `backend/app/models/api_call_log.py`（如存在）
- Read: `backend/tests/unit/test_*saihu*.py`、`backend/tests/unit/test_*sync*.py`
- Create: `docs/superpowers/scorecard/M1-saihu-integration.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**（来自 spec 第 3 节 M1）：D1 / D2 / D3 / D4 / D5 / D6 / D7 / D8 ✓；D9 N/A

**主战场维度**：D3 / D4 / D6

**P0 候选交叉引用**：
- P0-1 赛狐 API 对当前 IP 不可达 → 验证代码层是否为"出口 IP 切换/代理"留好接入点

- [ ] **Step 1: 列出并读取所有证据文件**

```bash
# 列出 saihu 模块文件
ls backend/app/saihu/ backend/app/saihu/endpoints/
# 列出 sync 模块文件
ls backend/app/sync/
# 找相关测试
find backend/tests -name "*saihu*" -o -name "*sync*"
```

然后用 Read 工具逐个读取上述文件。

- [ ] **Step 2: 运行相关测试并记录结果**

```bash
cd backend && .\.venv\Scripts\python.exe -m pytest tests/unit/ -k "saihu or sync" -v 2>&1 | tail -40
```

记录通过/失败的测试数量。

- [ ] **Step 3: 关键安全/可靠性 grep**

```bash
# Token 存储与密钥
grep -r "SAIHU_" backend/app/saihu/ backend/app/config.py
# 重试与限流
grep -rn "tenacity\|aiolimiter\|retry\|timeout" backend/app/saihu/
# IP 白名单 / 出口配置相关
grep -rn "proxy\|outbound\|whitelist\|allowed_ip" backend/app/
```

- [ ] **Step 4: 对照 Rubric 给 D1/D2/D3/D4/D5/D6/D7/D8 打分**

每个维度严格按 spec 第 2 节的判据匹配，并写入证据（文件:行号）+ "未达上一级的差距" + 疑点（⚠️）。

- [ ] **Step 5: 写入 M1 checkpoint 文件**

按 spec 第 5.2 节模板写入 `docs/superpowers/scorecard/M1-saihu-integration.md`。文件结构：

```markdown
# M1 赛狐集成 评分

## 1. 证据采集摘要
（文件清单、命令结果、grep 输出关键摘录）

## 2. 维度评分

### D1 功能完整性
- 得分：N/4
- 判据匹配：（引用 Rubric 原文）
- 支撑证据：
  - `backend/app/sync/xxx.py:line` — ...
- 未达上一级的差距：...
- 疑点：⚠️ ...

（D2-D8 重复，D9 标 N/A — 无直接 UI）

## 3. 模块得分
- 平均分（剔除 N/A）：X.XX / 4
- 主战场维度得分：D3=N D4=N D6=N

## 4. 本模块发现的关键问题
- 🔴 P0：（必须修，列具体动作）
- 🟡 P1：（强烈建议）
- 🟢 P2：（可延后）

## 5. P0/P1 候选清单交叉判定
- P0-1（赛狐 IP 不可达 / 出口接入点）：✅ 已实现 / ⚠️ 部分实现 / ❌ 未实现 — 引用证据

## 6. 给用户的确认问题
1. ⚠️ ...
2. ⚠️ ...
3. ⚠️ ...
```

- [ ] **Step 6: 更新 _calibration.md**

向 `_calibration.md` 的对应维度小节追加：

```markdown
### M1 赛狐集成
- D1=N — 理由：xxx
- D2=N — 理由：xxx
（每个评了的维度一行）
```

- [ ] **Step 7: 呈现摘要给用户**

向用户输出一个紧凑的摘要：模块得分、9 维度分数表、P0/P1 清单、3-5 个待确认疑点。等待用户回复 ✅ 通过 / 🔧 调整。

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M1-saihu-integration.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M1 赛狐集成评分封板"
```

---

### Task 2: M2 补货引擎 审计

**Files:**
- Read: `backend/app/engine/runner.py`、`backend/app/engine/step1_velocity.py` ~ `step6_timing.py`
- Read: `backend/app/engine/calc_engine_job.py`
- Read: `backend/tests/unit/test_engine_step1.py` ~ `test_engine_step6.py`
- Create: `docs/superpowers/scorecard/M2-engine.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D1 / D2 / D5 / D6 / D7 / D8 ✓；D3 ◦（低权重，仅看并发安全）；D4 N/A；D9 N/A

**主战场维度**：D1 / D6

**P0 候选交叉引用**：无直接 P0；P1-5（依赖 CVE 扫描）涉及 backend 整体

- [ ] **Step 1: 读取所有 engine 文件**

```bash
ls backend/app/engine/
```

逐个 Read 上述文件。

- [ ] **Step 2: 运行 engine 测试**

```bash
cd backend && .\.venv\Scripts\python.exe -m pytest tests/unit/test_engine_step*.py -v 2>&1 | tail -30
```

记录覆盖率（如可获取）。

- [ ] **Step 3: 关键并发/快照 grep**

```bash
grep -rn "advisory_xact_lock\|7429001" backend/app/engine/
grep -rn "snapshot\|JSONB" backend/app/engine/ backend/app/models/
grep -rn "load_in_transit" backend/app/engine/
```

- [ ] **Step 4: 对照 Rubric 给 D1/D2/D3◦/D5/D6/D7/D8 打分**

注意 D3 在 M2 是低权重（◦），重点看 advisory lock 的并发保护是否到位。

- [ ] **Step 5: 写入 M2 checkpoint 文件**

写入 `docs/superpowers/scorecard/M2-engine.md`，按 spec 5.2 模板。N/A 维度（D4、D9）直接标"N/A — 引擎无独立部署需求/无 UI"。

- [ ] **Step 6: 更新 _calibration.md**

追加 M2 各维度打分理由。

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M2-engine.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M2 补货引擎评分封板"
```

---

### Task 3: M3 建议单与推送 审计

**Files:**
- Read: `backend/app/api/suggestions/` 全部、`backend/app/pushback/purchase.py`
- Read: `backend/app/schemas/suggestion.py`、`backend/app/models/suggestion*.py`
- Read: 相关测试文件
- Create: `docs/superpowers/scorecard/M3-suggestions-pushback.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D1 / D2 / D3 / D5 / D6 / D7 / D8 ✓；D9 ◦（编辑表单校验反馈，主要在 M5）；D4 N/A

**主战场维度**：D1 / D6

**P0 候选交叉引用**：
- P0-2 公网假设覆盖 → 推送鉴权、参数校验
- P1-1 速率限制 → 推送端点是否有限流

- [ ] **Step 1: 读取证据文件**

```bash
ls backend/app/api/suggestions/ backend/app/pushback/
find backend/tests -name "*suggestion*" -o -name "*pushback*"
```

逐个 Read。

- [ ] **Step 2: 运行相关测试**

```bash
cd backend && .\.venv\Scripts\python.exe -m pytest tests/unit/ -k "suggestion or pushback" -v 2>&1 | tail -30
```

- [ ] **Step 3: 关键 grep（状态机 / 幂等 / JSONB 不可变）**

```bash
grep -rn "draft\|partial\|pushed\|archived\|error" backend/app/api/suggestions/ backend/app/pushback/
grep -rn "dedupe_key\|push_saihu" backend/app/pushback/ backend/app/tasks/
grep -rn "country_breakdown" backend/app/
```

- [ ] **Step 4: 对照 Rubric 打分 D1/D2/D3/D5/D6/D7/D8/D9◦**

- [ ] **Step 5: 写入 M3 checkpoint 文件**

写入 `docs/superpowers/scorecard/M3-suggestions-pushback.md`。

- [ ] **Step 6: 更新 _calibration.md**

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M3-suggestions-pushback.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M3 建议单与推送评分封板"
```

---

### Task 4: M4 任务队列 审计

**Files:**
- Read: `backend/app/tasks/queue.py`、`backend/app/tasks/reaper.py`、`backend/app/tasks/jobs/*.py`
- Read: `backend/app/models/task_run.py`（或对应位置）
- Read: 相关 alembic migration（task_run 表）
- Read: 相关测试
- Create: `docs/superpowers/scorecard/M4-task-queue.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D1 / D2 / D4 / D5 / D6 / D7 / D8 ✓；D3 ◦；D9 N/A

**主战场维度**：D5 / D6

- [ ] **Step 1: 读取证据文件**

```bash
ls backend/app/tasks/ backend/app/tasks/jobs/
find backend/alembic -name "*task_run*"
find backend/tests -name "*task*queue*" -o -name "*reaper*"
```

逐个 Read。

- [ ] **Step 2: 运行测试**

```bash
cd backend && .\.venv\Scripts\python.exe -m pytest tests/unit/ -k "task or queue or reaper" -v 2>&1 | tail -30
```

- [ ] **Step 3: 关键 grep**

```bash
grep -rn "PROCESS_ENABLE_WORKER\|PROCESS_ENABLE_REAPER\|PROCESS_ENABLE_SCHEDULER" backend/
grep -rn "lease\|heartbeat\|dedupe" backend/app/tasks/
grep -rn "SKIPPED\|skipped" backend/app/tasks/
```

- [ ] **Step 4: 对照 Rubric 打分**

- [ ] **Step 5: 写入 M4 checkpoint 文件**

写入 `docs/superpowers/scorecard/M4-task-queue.md`。

- [ ] **Step 6: 更新 _calibration.md**

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M4-task-queue.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M4 任务队列评分封板"
```

---

### Task 5: M5 前端数据页 审计

**Files:**
- Read: `frontend/src/views/`（所有 view）
- Read: `frontend/src/components/PageSectionCard.vue`、`TablePaginationBar.vue`、Dashboard 组件
- Read: `frontend/src/utils/format.ts`、`warehouse.ts`、`countries.ts`、`status.ts`、`tableSort.ts`
- Read: `frontend/vite.config.ts`、`frontend/package.json`
- Read: 相关 vitest 测试
- Create: `docs/superpowers/scorecard/M5-frontend.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D1 / D2 / D3 / D4 / D6 / D7 / D8 / D9 ✓；D5 ◦（前端错误上报可能未实现）

**主战场维度**：D9 / D1 / D8

**P0 候选交叉引用**：
- P0-2 公网假设覆盖 → XSS、token 存储位置

- [ ] **Step 1: 读取证据文件**

```bash
ls frontend/src/views/ frontend/src/components/ frontend/src/utils/
find frontend/src -name "*.test.ts"
```

按子目录批量 Read。

- [ ] **Step 2: 运行类型检查与构建**

```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | tail -10
cd frontend && npx vite build 2>&1 | tail -20
```

记录是否通过、bundle 体积、vendor 分包情况。

- [ ] **Step 3: 关键 grep**

```bash
# token 存储
grep -rn "localStorage\|sessionStorage" frontend/src/
# XSS 风险
grep -rn "v-html\|innerHTML\|dangerouslySetInnerHTML" frontend/src/
# 错误处理与降级
grep -rn "ElMessage.error\|catch" frontend/src/views/ frontend/src/api/
# PageSectionCard 一致性
grep -rln "PageSectionCard" frontend/src/views/
```

- [ ] **Step 4: 对照 Rubric 打分 D1/D2/D3/D4/D5◦/D6/D7/D8/D9**

- [ ] **Step 5: 写入 M5 checkpoint 文件**

写入 `docs/superpowers/scorecard/M5-frontend.md`。

- [ ] **Step 6: 更新 _calibration.md**

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M5-frontend.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M5 前端数据页评分封板"
```

---

### Task 6: M6 认证与配置 审计

**Files:**
- Read: `backend/app/api/auth.py`（或对应位置）、`backend/app/api/deps.py`
- Read: `backend/app/models/login_attempt.py`、`backend/app/models/global_config.py`
- Read: `backend/app/config.py`（JWT_SECRET、密钥相关配置）
- Read: `backend/alembic/versions/*login_attempt*.py`
- Read: `backend/tests/unit/test_auth_login.py`、`backend/tests/unit/test_runtime_settings.py`、`backend/tests/unit/test_config_schema.py`
- Read: `frontend/src/views/LoginView.vue`（或对应路径）
- Create: `docs/superpowers/scorecard/M6-auth-config.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D1 / D2 / D3 / D4 / D5 / D6 / D7 / D9 ✓；D8 ◦

**主战场维度**：D3（公网核心）

**P0 候选交叉引用**：
- P0-2 公网假设覆盖 → JWT 强度、密钥管理
- P0-5 JWT_SECRET 初始生成与轮换流程
- P1-6 X-Forwarded-For 信任来源

- [ ] **Step 1: 读取证据文件**

```bash
find backend/app -name "auth*.py" -o -name "*login*.py"
find backend/app -name "config.py" -o -name "global_config.py"
find backend/alembic -name "*login*"
find frontend/src -name "*Login*"
```

逐个 Read。

- [ ] **Step 2: 运行测试**

```bash
cd backend && .\.venv\Scripts\python.exe -m pytest tests/unit/test_auth_login.py tests/unit/test_config_schema.py tests/unit/test_runtime_settings.py -v 2>&1 | tail -20
```

- [ ] **Step 3: 关键安全 grep**

```bash
# JWT 算法与密钥来源
grep -rn "JWT_SECRET\|HS256\|jwt.encode\|jwt.decode" backend/
# 密码 hash
grep -rn "bcrypt\|argon2\|passlib" backend/
# X-Forwarded-For 信任
grep -rn "X-Forwarded-For\|X-Real-IP\|forwarded" backend/
# 登录锁定
grep -rn "login_attempt\|locked\|lockout" backend/
# 密钥硬编码检查
grep -rn "secret\s*=\|password\s*=" backend/app/ | grep -v "test\|example"
```

- [ ] **Step 4: 对照 Rubric 打分**

D3 安全是核心，必须详细评估每条 Rubric 子项（JWT 强度、环境变量、Pydantic 校验、密码 hash、登录锁定、速率限制、CORS/CSRF、CVE 扫描、日志脱敏、TLS、安全 headers）。

- [ ] **Step 5: 写入 M6 checkpoint 文件**

写入 `docs/superpowers/scorecard/M6-auth-config.md`。在"P0/P1 候选清单交叉判定"小节，明确判定 P0-2 / P0-5 / P1-6 三项。

- [ ] **Step 6: 更新 _calibration.md**

D3 维度的标尺记录尤为重要——这是后续 M3/M5/M7/M8 打 D3 时的对照基准。

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M6-auth-config.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M6 认证与配置评分封板"
```

---

### Task 7: M7 基础设施 审计

**Files:**
- Read: `backend/app/db/base.py`、`backend/app/db/session.py`
- Read: `backend/alembic/env.py`、`backend/alembic/versions/*.py`（重点看 initial migration）
- Read: `backend/app/core/exceptions.py`、`backend/app/core/middleware.py`、`backend/app/core/timezone.py`
- Read: `backend/app/main.py`
- Read: `backend/tests/unit/test_health_endpoints.py`
- Create: `docs/superpowers/scorecard/M7-infrastructure.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D2 / D3 / D4 / D5 / D6 / D7 / D8 ✓；D1 ◦；D9 N/A

**主战场维度**：D5（结构化日志主战场）/ D4

**P0 候选交叉引用**：
- P1-2 CORS allowed_origins
- P1-4 5xx traceback 泄漏

- [ ] **Step 1: 读取证据文件**

```bash
ls backend/app/db/ backend/app/core/ backend/alembic/ backend/alembic/versions/
```

逐个 Read。

- [ ] **Step 2: 运行 health 测试**

```bash
cd backend && .\.venv\Scripts\python.exe -m pytest tests/unit/test_health_endpoints.py -v 2>&1 | tail -20
```

- [ ] **Step 3: 关键 grep**

```bash
# 结构化日志
grep -rn "structlog\|get_logger" backend/app/
# request_id 中间件
grep -rn "request_id\|X-Request-ID" backend/app/core/
# 异常体系
grep -rn "BusinessError\|HTTPException" backend/app/core/exceptions.py
# CORS
grep -rn "CORSMiddleware\|allow_origins" backend/app/main.py backend/app/core/
# 数据库连接池
grep -rn "pool_size\|pool_pre_ping\|max_overflow" backend/app/db/
```

- [ ] **Step 4: 对照 Rubric 打分**

D5 可观测性是 M7 主战场，详细评估结构化日志 + request_id 绑定 + 健康检查的完整度。

- [ ] **Step 5: 写入 M7 checkpoint 文件**

写入 `docs/superpowers/scorecard/M7-infrastructure.md`。

- [ ] **Step 6: 更新 _calibration.md**

D5 维度的标尺记录是 M1/M3/M4/M6/M8 打 D5 的基准。

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M7-infrastructure.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M7 基础设施评分封板"
```

---

### Task 8: M8 部署与交付 审计

**Files:**
- Read: `deploy/docker-compose.yml`、`deploy/Caddyfile`、`deploy/.env.example`
- Read: `deploy/scripts/deploy.sh`、`migrate.sh`、`pg_backup.sh`、`restore_db.sh`、`rollback.sh`、`validate_env.sh`、`smoke_check.sh`
- Read: `backend/Dockerfile`
- Read: `docs/deployment.md`、`docs/runbook.md`、`docs/onboarding.md`
- Read: `.github/workflows/*.yml`（CI/CD 配置）
- Create: `docs/superpowers/scorecard/M8-deployment.md`
- Modify: `docs/superpowers/scorecard/_calibration.md`

**适用维度**：D3 / D4 / D6 / D7 ✓；D2 / D5 / D8 ◦；D1 / D9 N/A

**主战场维度**：D3（公网核心）/ D4（核心）/ D7（核心）

**P0 候选交叉引用**：
- P0-3 域名 / TLS 证书自动续签
- P0-4 数据库备份存放策略
- P0-5 JWT_SECRET 初始生成与轮换流程
- P1-1 速率限制
- P1-3 OpenAPI 文档关闭验证
- P1-5 依赖 CVE 扫描

- [ ] **Step 1: 读取证据文件**

```bash
ls deploy/ deploy/scripts/
ls .github/workflows/ 2>&1 || echo "no .github/workflows"
```

逐个 Read 上述文件。

- [ ] **Step 2: 检查 deploy 脚本可执行性**

```bash
ls -la deploy/scripts/*.sh
```

记录哪些脚本有 +x、哪些没有。

- [ ] **Step 3: 关键 grep**

```bash
# Caddy 安全 headers
grep -in "Strict-Transport-Security\|X-Frame-Options\|Content-Security-Policy\|hsts" deploy/Caddyfile
# 资源限制
grep -in "mem_limit\|cpus\|deploy:" deploy/docker-compose.yml
# CVE 扫描
grep -rn "pip-audit\|safety\|npm audit" .github/ deploy/scripts/
# 密钥管理与备份
grep -in "BACKUP\|S3\|encrypt" deploy/scripts/pg_backup.sh
# OpenAPI 关闭
grep -rn "APP_DOCS_ENABLED" backend/app/ deploy/
```

- [ ] **Step 4: 对照 Rubric 打分**

D3/D4/D7 三个主战场维度详细评估；P0/P1 候选必须逐项给出"已实现/部分/未实现"判定。

- [ ] **Step 5: 写入 M8 checkpoint 文件**

写入 `docs/superpowers/scorecard/M8-deployment.md`。

- [ ] **Step 6: 更新 _calibration.md**

- [ ] **Step 7: 呈现摘要给用户**

- [ ] **Step 8: 用户确认后 commit**

```bash
git add docs/superpowers/scorecard/M8-deployment.md docs/superpowers/scorecard/_calibration.md
git commit -m "docs(scorecard): M8 部署与交付评分封板"
```

---

## Phase 2: 聚合与最终报告

### Task 9: 计算评分矩阵与维度/汇总组得分

**Files:**
- Read: `docs/superpowers/scorecard/M1-saihu-integration.md` 至 `M8-deployment.md`
- Create: `docs/superpowers/scorecard/_aggregate.md`（中间计算文件）

- [ ] **Step 1: 提取所有 8 个模块的评分**

逐个 Read 8 个 M{n}-*.md 文件，提取每个模块的 9 维度分数（含 N/A 标记），整理为内存中的二维表。

- [ ] **Step 2: 构建 8 × 9 评分矩阵**

写入 `docs/superpowers/scorecard/_aggregate.md`，内容包含：

```markdown
# 评分矩阵聚合表

## 1. 8 × 9 矩阵

| 模块 \ 维度 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | 模块均分 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| M1 赛狐集成 | n | n | n | n | n | n | n | n | N/A | x.xx |
| M2 补货引擎 | n | n | n | N/A | n | n | n | n | N/A | x.xx |
| ... | | | | | | | | | | |
| **维度均分** | x.xx | x.xx | ... | | | | | | | |
```

按 spec 第 1.4 节的算法计算：
- 模块均分 = 该模块所有非 N/A 格的算术平均
- 维度均分 = 该维度所有非 N/A 格的算术平均

- [ ] **Step 3: 计算 4 汇总组得分**

按 spec 第 4.1/4.2 节的权重表：

```
G1 能不能上线 = (D1×3 + D2×1 + D3×2 + D4×3) / 9
G2 上线后能不能稳 = (D2×1 + D3×2 + D5×2 + D6×3 + D8×2) / 10
G3 坏了能不能救 = (D4×2 + D5×3 + D6×2 + D7×1) / 8
G4 用着顺不顺 = (D1×1 + D2×2 + D7×2 + D8×1 + D9×3) / 9
```

将结果写入 `_aggregate.md`：

```markdown
## 2. 4 汇总组得分

| 组 | 计算 | 得分 |
|---|---|:--:|
| G1 能不能上线 | ... | x.xx |
| G2 上线后能不能稳 | ... | x.xx |
| G3 坏了能不能救 | ... | x.xx |
| G4 用着顺不顺 | ... | x.xx |
| **总体得分** | (G1+G2+G3+G4)/4 | x.xx |
```

- [ ] **Step 4: 应用交付门槛规则**

按 spec 第 4.3 节判定：

```
✅ 达标：总体 ≥ 2.5  且  4 组中没有任何一组 < 2.0  且  D3/D4/D6 维度均 ≥ 3.0
⚠️ 待补强：总体 ≥ 2.0 但不满足上述任一条件
❌ 不可上线：总体 < 2.0 或 任一汇总组 < 1.5 或 D3 < 2
```

将判定结果与具体原因（哪几条门槛未达到）写入 `_aggregate.md`。

- [ ] **Step 5: 提交聚合文件**

```bash
git add docs/superpowers/scorecard/_aggregate.md
git commit -m "docs(scorecard): 完成 8 模块评分聚合计算"
```

---

### Task 10: 汇总 P0/P1/P2 行动清单

**Files:**
- Read: 8 个 M{n}-*.md 中的"本模块发现的关键问题"小节
- Modify: `docs/superpowers/scorecard/_aggregate.md`

- [ ] **Step 1: 收集所有模块的 P0/P1/P2 发现**

逐个读取 M1-M8 的"4. 本模块发现的关键问题"小节，按优先级和模块分组。

- [ ] **Step 2: 去重与合并**

跨模块的重复项合并为一条（例如"无速率限制"可能在 M3/M6/M8 都被提到，合并为一条但标注影响范围）。

- [ ] **Step 3: 排序**

按以下顺序：
1. 🔴 P0 阻塞（不修则不可上线）
2. 🟡 P1 强烈建议（修了能升 G1/G2 一个等级）
3. 🟢 P2 可延后（不影响交付门槛）

- [ ] **Step 4: 追加到 _aggregate.md**

在 `_aggregate.md` 末尾追加：

```markdown
## 3. 跨模块行动清单

### 🔴 P0 阻塞（必须在交付前修）
1. **[标题]** — 影响模块：Mn / Mn — 具体动作：...
2. ...

### 🟡 P1 强烈建议
1. ...

### 🟢 P2 可延后
1. ...
```

- [ ] **Step 5: 提交**

```bash
git add docs/superpowers/scorecard/_aggregate.md
git commit -m "docs(scorecard): 汇总 P0/P1/P2 跨模块行动清单"
```

---

### Task 11: 撰写并提交最终报告

**Files:**
- Read: `docs/superpowers/scorecard/_aggregate.md`、所有 M{n}-*.md
- Create: `docs/superpowers/specs/2026-04-XX-delivery-readiness-report.md`（XX 替换为实际完成日期）

- [ ] **Step 1: 确定报告日期**

```bash
date +%Y-%m-%d
```

记录今日日期，作为报告文件名的一部分。

- [ ] **Step 2: 按 spec 第 5.4 节模板撰写最终报告**

写入 `docs/superpowers/specs/{date}-delivery-readiness-report.md`，结构如下：

```markdown
# Restock System 云交付就绪度评估报告

> 评估日期：YYYY-MM-DD
> 评估目标：A+B+C 综合场景 + 公网交付（代码与配置层面）
> 评估方法：5 级 Rubric × 协同审计（方案 B 模块分批）
> Spec：docs/superpowers/specs/2026-04-11-delivery-readiness-scorecard-design.md

## 1. 执行摘要

- **总体得分**：X.XX / 4
- **交付门槛判定**：✅ 达标 / ⚠️ 待补强 / ❌ 不可上线
- **4 汇总组得分**：
  - G1 能不能上线：X.XX
  - G2 上线后能不能稳：X.XX
  - G3 坏了能不能救：X.XX
  - G4 用着顺不顺：X.XX
- **TOP 5 P0 阻塞项**：
  1. ...

## 2. 评分矩阵

（从 _aggregate.md 拷贝 8×9 矩阵 + 行/列均分）

## 3. 4 汇总组详细分析

### G1 能不能上线（X.XX）
- 主要拉分维度：...
- 主要提分维度：...
- 改进路径：...

（G2 / G3 / G4 重复）

## 4. 9 维度逐项分析

### D1 功能完整性（均分 X.XX）
- 强项模块：...
- 弱项模块：...
- 共性问题：...

（D2 - D9 重复）

## 5. 8 模块逐项分析

### M1 赛狐集成（均分 X.XX）
- 主战场维度表现：D3=N D4=N D6=N
- 关键发现：...
- 详细 checkpoint：[M1-saihu-integration.md](../scorecard/M1-saihu-integration.md)

（M2 - M8 重复）

## 6. 补强行动清单（按优先级）

### 🔴 P0 阻塞
（从 _aggregate.md 拷贝）

### 🟡 P1 强烈建议
（同上）

### 🟢 P2 可延后
（同上）

## 7. 重新评估建议

完成 P0 后建议重跑评估的范围：
- 必须重测的模块：...
- 必须重测的维度：...
- 可保留原分数的模块：...

## 8. 范围声明（原 spec 1.2）

本评估仅覆盖代码与配置层面就绪度，不包括服务器环境实地审计。
完成 P0/P1 后部署到云服务器时，仍需补充进行：
- 服务器规格与资源验证
- 防火墙与入站规则配置
- 域名与 DNS 配置
- TLS 证书签发与续签验证
- 监控告警通道实地连通性测试
```

- [ ] **Step 3: 提交最终报告**

```bash
git add docs/superpowers/specs/*-delivery-readiness-report.md
git commit -m "docs(superpowers): 云交付就绪度评估最终报告"
```

- [ ] **Step 4: 更新 PROGRESS.md 并触发文档同步协议**

按 AGENTS.md 第 9 节，新增评估报告属于 docs 类变更。在 `docs/PROGRESS.md` 第 3 节"近期重大变更"追加一条：

```markdown
### 3.X 云交付就绪度评估完成
- 完成 8 模块 × 9 维度评分（64 计分格）
- 总体得分 X.XX / 4，交付门槛判定 ✅/⚠️/❌
- TOP P0 阻塞项 N 个，P1 建议项 M 个
- 详见 `docs/superpowers/specs/{date}-delivery-readiness-report.md`
```

并把"最近更新"日期改为今日。

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): 同步云交付就绪度评估完成"
```

- [ ] **Step 5: 通知用户评估完成**

向用户输出一段总结：
- 总体得分与判定
- 4 汇总组得分
- TOP 5 P0 阻塞项
- 报告文件路径
- 下一步建议（按 P0 顺序补强 / 重跑评估时机）

---

## Plan Self-Review Checklist（执行前一次性确认）

执行任何任务前，先确认：

- [ ] 已读完 spec 第 2 节（9 维度 Rubric）
- [ ] 已读完 spec 第 3 节（8 模块定义）
- [ ] 已读完 spec 第 6 节（P0/P1 候选清单）
- [ ] 已读完 AGENTS.md 协作规则与文档同步协议
- [ ] 当前分支为 `001-saihu-replenishment` 或独立 worktree

执行过程中：

- [ ] 每完成一个模块的 checkpoint，必须等用户 ✅ 确认后才能进入下一个
- [ ] 标尺一致性记录 `_calibration.md` 必须随每个模块同步更新
- [ ] 任何打分都必须配证据引用（文件:行号），不允许"凭印象"打分
- [ ] N/A 必须给出原因，不能直接留空

---

## 备注

- **本计划是流程脚本，不是代码实现**。每个任务是"读代码 + 应用 Rubric + 写报告"，不涉及修改业务代码
- **总投入估算**：约 11-13 个对话回合（8 个模块 checkpoint + 3 个 Phase 2 task + 视情况追加澄清回合）
- **可中断**：每个模块封板 commit 后即可暂停，下次继续从下一个模块开始
- **回滚机制**：如发现某个模块的判据有问题，可重跑该模块的 Task，覆盖对应 M{n}-*.md 文件并更新 _calibration.md
