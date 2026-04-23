# CodeRabbit PR #13 Follow-up Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补修 CodeRabbit 在 PR #13 留的 6 条 actionable（#1/#2/#3/#4/#5/#8，#5 从 FIX LATER 升级到 FIX NOW；#6 DECLINE 不修；#7 FIX LATER 保持），然后 CI 再跑一轮再 merge PR #13。

**Architecture:**
- Phase A — **代码/配置**（Fix 1-3）：Settings env 下界校验 / 测试断言补漏 / shell 变量引号
- Phase B — **文档**（Fix 4-6）：runbook 命名 + 占位符 / runbook SOP 命令改 compose-agnostic / findings 计数自洽
- Phase C — **验证 + PR 续推**：本地 mypy / ruff / pytest（unit parallel + integration serial）全绿 → push

所有 6 条都是 1-5 行的 localized 修改，无 refactor 风险。TDD 不适用于文档修改；代码修改里 Fix 1 + Fix 2 按"先改测试 / 再改代码 / 再跑测试"的 TDD 走。

**Tech Stack:** Python 3.11 + pytest + pytest-xdist（分片 unit 测试）；Bash（shell 引号）；Markdown（runbook / findings doc）。

**Pre-flight:**
- 当前分支：`feat/post-audit-round-2`（PR #13 OPEN / CLEAN / CI green + CodeRabbit 已 review）
- base commit：`2d19d2e` (head of branch after plan doc commit)
- dev 容器 healthy

---

## 文件结构全景

- Modify: `backend/app/config.py`（`validate_settings` 加 1 处负值检查）
- Modify: `backend/tests/unit/test_retention_job.py`（1 行 assert 补漏）
- Modify: `deploy/scripts/restore_db.sh:55`（echo 变量双引号包裹）
- Modify: `docs/runbook.md:591,597`（`.env.production` 命名一致化 + 替换 `<维护者姓名>` 占位）
- Modify: `docs/runbook.md:643,660,675,680,683,689,709,724,727`（约 9 处 `restock-dev-*` / `localhost:8088` 泛化）
- Modify: `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md`（header 计数 + 汇总表 A-1 + 补 3 条 Ack）

---

## Phase A — 代码/配置 Fix

### Fix-1 (CodeRabbit #1): `retention_stuck_generating_hours` 下界校验

**Why:** CodeRabbit 🟠 Major — 负值（如 `-24`）会让 `cutoff = now_beijing() - timedelta(hours=-24)` 变成"未来 24 小时"，`exported_at < cutoff` WHERE 会把**所有**非 failed/ready 的 generating snapshot 标 failed（包括刚开始生成的）。与 `0 = 禁用` 的文档契约违反。

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/unit/test_runtime_settings.py`（新增/补充断言）

- [ ] **Step 1: 检查现有 test_runtime_settings 结构**

```bash
ls /e/Ai_project/restock_system/backend/tests/unit/test_runtime_settings.py 2>&1
grep -n "def test_\|validate_settings\|JWT_SECRET must be at least" /e/Ai_project/restock_system/backend/tests/unit/test_runtime_settings.py 2>&1 | head
```

判断：文件存在 → append 一个新 test；不存在 → 新建（按现有 `validate_settings` 测试风格）。

- [ ] **Step 2: 写失败测试**

Append to `backend/tests/unit/test_runtime_settings.py`（如无此文件，创建最小 skeleton；其他 validate_settings 的测试应已有）:

```python
def test_retention_stuck_generating_hours_rejects_negative(monkeypatch) -> None:
    """负值会让 cutoff 跑到未来，静默把所有 generating snapshot 标 failed。"""
    import pytest
    from app.config import Settings, validate_settings

    monkeypatch.setenv("RETENTION_STUCK_GENERATING_HOURS", "-1")
    # 其他必需 prod 校验跳过：用 dev env + 占位 secrets
    monkeypatch.setenv("APP_ENV", "development")

    with pytest.raises(ValueError, match="RETENTION_STUCK_GENERATING_HOURS"):
        validate_settings(Settings())
```

- [ ] **Step 3: 跑测试确认失败**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)/unit/test_runtime_settings.py" restock-dev-backend:/tmp/tests/unit/test_runtime_settings.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages python -m pytest tests/unit/test_runtime_settings.py::test_retention_stuck_generating_hours_rejects_negative -v --no-header 2>&1 | tail -10"
```

Expected: `DID NOT RAISE` or `FAILED` — 当前 `validate_settings` 不校验该字段。

- [ ] **Step 4: 实现校验**

Edit `backend/app/config.py` — 找到 `validate_settings` 函数中已有校验块（`push_auto_retry_times < 1` 附近），在同一 `errors.append` 串里加一行：

```python
    if settings.retention_stuck_generating_hours < 0:
        errors.append("RETENTION_STUCK_GENERATING_HOURS must be >= 0 (0 disables)")
```

具体位置：该检查紧随 `push_auto_retry_times` 的校验之后（保持按字段顺序分组）。

- [ ] **Step 5: 跑测试确认通过**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/app && pwd -W)/config.py" restock-dev-backend:/app/app/config.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages python -m pytest tests/unit/test_runtime_settings.py -v --no-header 2>&1 | tail -10"
```

Expected: 新测试 passed + 其他已有 `test_runtime_settings` 测试仍 passed。

- [ ] **Step 6: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/app/config.py backend/tests/unit/test_runtime_settings.py
git -C /e/Ai_project/restock_system commit -m "fix(backend): validate_settings 拒绝 retention_stuck_generating_hours < 0

CodeRabbit 🟠 Major (PR #13 review #1)：负值会让 cutoff 跑到未来，
retention_purge_job 会把所有正在生成的 snapshot 误标 failed，违反
'0 = 禁用' 的文档契约。

按现有 validate_settings 风格加一条 errors.append 校验 + 对应单测。"
```

---

### Fix-2 (CodeRabbit #2): `test_purge_stuck_generating_marks_rows_failed` 补断言 `exported_at`

**Why:** CodeRabbit 🟡 Minor — 测试的 comment 说"SQL 含 generation_status='generating' + 时间阈值"，但 assertion 只 verify `"generation_status" in compiled`；若未来有人 merge 掉 `exported_at < cutoff` 的 WHERE，测试仍 pass，但 retention 会标所有 generating（不管年龄）。

**Files:**
- Modify: `backend/tests/unit/test_retention_job.py`

- [ ] **Step 1: 补断言**

Edit `backend/tests/unit/test_retention_job.py:234-236`（当前块是 `test_purge_stuck_generating_marks_rows_failed`）。

当前代码（第 234-236 行左右）:

```python
    # SQL 含 generation_status='generating' + 时间阈值
    compiled = str(db.executed[0])
    assert "generation_status" in compiled.lower()
```

加一行断言 `exported_at`:

```python
    # SQL 含 generation_status='generating' + 时间阈值（exported_at < cutoff）
    compiled = str(db.executed[0]).lower()
    assert "generation_status" in compiled
    assert "exported_at" in compiled, (
        "WHERE 子句丢失 exported_at 时间阈值 → 会标所有 generating 而不管年龄"
    )
```

- [ ] **Step 2: 跑测试**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)/unit/test_retention_job.py" restock-dev-backend:/tmp/tests/unit/test_retention_job.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages python -m pytest tests/unit/test_retention_job.py -v --no-header 2>&1 | tail -15"
```

Expected: 15 passed（12 原有 + 3 stuck_generating 测试，其中 `_marks_rows_failed` 现在多断 1 条）。

- [ ] **Step 3: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/tests/unit/test_retention_job.py
git -C /e/Ai_project/restock_system commit -m "test(backend): purge_stuck_generating SQL 测试补 exported_at 断言

CodeRabbit 🟡 Minor (PR #13 review #2)：原测试注释说'SQL 含 generation_status
+ 时间阈值'，但只断言了 generation_status。若未来 WHERE 丢失 exported_at 条件，
retention 会标所有 generating snapshot 而不管年龄，测试仍 pass。

补一行 assert 'exported_at' in compiled 关上这个缝。"
```

---

### Fix-3 (CodeRabbit #3): `restore_db.sh` 回退提示 echo 变量加引号

**Why:** CodeRabbit 🟡 Minor — `restore_db.sh:55` 的 `echo "[safety] 如 restore 失败，可用 bash $0 $SAFETY_DUMP 回退。"` 未用双引号包裹 `$0` / `$SAFETY_DUMP`，路径含空格会产生坏的复制粘贴命令。incident 时用的 safety hint 不能自己坏。

**Files:**
- Modify: `deploy/scripts/restore_db.sh`

- [ ] **Step 1: 定位 + 修**

Edit `deploy/scripts/restore_db.sh:55`:

当前：

```bash
    echo "[safety] 如 restore 失败，可用 bash $0 $SAFETY_DUMP 回退。"
```

改为：

```bash
    echo "[safety] 如 restore 失败，可用 bash \"$0\" \"$SAFETY_DUMP\" 回退。"
```

（反斜杠 `\"` 转义双引号，让输出形如 `bash "script path.sh" "backup path.sql.gz"`。）

- [ ] **Step 2: 语法验证**

```bash
bash -n /e/Ai_project/restock_system/deploy/scripts/restore_db.sh && echo "syntax OK"
```

Expected: `syntax OK`。

- [ ] **Step 3: 手工渲染确认**

运行一个最小 bash 验证 echo 正确输出：

```bash
bash -c '
SAFETY_DUMP="/path with spaces/backup.sql.gz"
echo "[safety] 如 restore 失败，可用 bash \"$0\" \"$SAFETY_DUMP\" 回退。"
' fake-script.sh
```

Expected 输出:
```
[safety] 如 restore 失败，可用 bash "fake-script.sh" "/path with spaces/backup.sql.gz" 回退。
```

（`$0` 展开是 `fake-script.sh`，`$SAFETY_DUMP` 展开完整路径，引号包裹。）

- [ ] **Step 4: Commit**

```bash
git -C /e/Ai_project/restock_system add deploy/scripts/restore_db.sh
git -C /e/Ai_project/restock_system commit -m "fix(deploy): restore_db.sh 回退提示给 \$0 / \$SAFETY_DUMP 加引号

CodeRabbit 🟡 Minor (PR #13 review #3)：echo 里的 \$0 和 \$SAFETY_DUMP
未引号包裹，含空格的路径生成的复制粘贴命令会坏。incident 时用的 safety
hint 不能自己坏。

改为 \\\"\$0\\\" 和 \\\"\$SAFETY_DUMP\\\"（echo 输出里仍是双引号）。"
```

---

## Phase B — 文档 Fix

### Fix-4 (CodeRabbit #4): runbook `.env` 命名一致化 + 占位符填充

**Why:** CodeRabbit 🟠 Major — §6.4 同一小节里先说"`.env.production` 必须包含"，后面步骤又说 `scp .../.env.production user@prod:/.../.env`（目标文件名 drop 了 `.production`）；`<维护者姓名>` 占位符**在提交前应被 grep 出来警告**但没有。incident 压力下命名歧义会让操作者犯错。

**Files:**
- Modify: `docs/runbook.md`

- [ ] **Step 1: 读当前 §6.4**

```bash
sed -n '580,600p' /e/Ai_project/restock_system/docs/runbook.md
```

确认线号与现状。

- [ ] **Step 2: 命名一致化**

Edit `docs/runbook.md:596`，当前：

```markdown
2. **复制到目标机器**：`scp <local>/.env.production user@prod:/path/to/restock_system/.env`
```

改为：

```markdown
2. **复制到目标机器**：`scp <local>/.env.production user@prod:/path/to/restock_system/.env.production`
```

（目标路径保留 `.env.production` 后缀，与 `deploy/.env.production.example` / `validate_env.sh` 的默认加载一致。）

- [ ] **Step 3: 替换占位符**

Edit `docs/runbook.md:591`，当前：

```markdown
> **责任**：当前由 <维护者姓名> 保管完整 secrets 副本。变更 / 离职时必须把最新副本同步给接班人。
```

改为：

```markdown
> **责任**：当前由 <填写负责人姓名或团队别名> 保管完整 secrets 副本。变更 / 离职时必须把最新副本同步给接班人。此占位符必须在交付部署前由项目负责人替换为实际姓名。
```

（CodeRabbit suggested `<填写负责人姓名>` — 这里用略长版本更醒目，同时留 `<...>` 尖括号明示"待填"。实际项目负责人姓名由用户自己改，不写进 PR。）

- [ ] **Step 4: 验证**

```bash
grep -n "维护者姓名\|.env.production user@prod" /e/Ai_project/restock_system/docs/runbook.md
```

Expected:
- `维护者姓名` 0 hits（已替换为 `填写负责人姓名或团队别名`）
- `.env.production user@prod:/.../.env` 0 hits（已改为 `.env.production`）

- [ ] **Step 5: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/runbook.md
git -C /e/Ai_project/restock_system commit -m "docs(runbook): §6.4 secrets 恢复命名一致化 + 换占位符提示

CodeRabbit 🟠 Major (PR #13 review #4)：
- §6.4.2 恢复步骤 2 的 scp 目标从 .env 改为 .env.production，与本节开头的
  '.env.production 必须包含的敏感项' 和 deploy/.env.production.example 保持
  命名一致。incident 下命名歧义会误导操作者把文件 scp 到错位置导致
  validate_env.sh fail。
- <维护者姓名> 占位符改为 <填写负责人姓名或团队别名>，显式标注'此占位符
  必须在交付部署前由项目负责人替换'，否则 runbook 读者会以为占位符是
  约定俗成的代指。"
```

---

### Fix-5 (CodeRabbit #5): runbook §8 SOP 命令改 compose-agnostic

**Why:** CodeRabbit 🟠 Major — §8 章节标题"部署后验证"面向 prod，但命令用了 `docker exec restock-dev-backend` / `localhost:8088` 这类**只在 dev compose 里存在**的名字。ops 在生产上复制会 fail。泛化到 `docker compose -f <file> exec <service>` + 占位域名形式，dev 和 prod 都能用（只需换 compose 文件路径）。

**Files:**
- Modify: `docs/runbook.md`

- [ ] **Step 1: 读当前 §8**

```bash
sed -n '640,745p' /e/Ai_project/restock_system/docs/runbook.md
```

定位 3 个命令块：
- §8.1 Retention purge 手工触发（~line 643, 660）
- §8.2 Dashboard stale（~line 675, 680, 683, 689）
- §8.3 Excel purged（~line 709, 724 若存在）

- [ ] **Step 2: 在 §8 开头加一个"命令约定"小段**

Edit `docs/runbook.md` — 在 §8 标题下方第一段（现在是"> 首次部署或每季度演练一次..."）之后，加一个新段落：

```markdown
### 8.0 命令约定

本节 SOP 用 `docker compose` 语法，适合任何环境，但需先在 shell 里 export 对应 compose 文件路径：

```bash
# dev（本地）
export COMPOSE_FILES="-f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev"
export API_HOST="http://localhost:8088"

# prod
export COMPOSE_FILES="-f deploy/docker-compose.yml --env-file deploy/.env.production"
export API_HOST="https://<your-domain>"
```

下面所有命令用 `docker compose $COMPOSE_FILES exec backend ...` / `$API_HOST/api/...` 形式。若忘 export 直接跑会 fail，这是刻意的 —— 强制操作者想清楚跑哪个环境。
```

- [ ] **Step 3: 改 §8.1 命令块（enqueue retention + 看 logs）**

Edit `docs/runbook.md:643` 开始的代码块：

当前：

```bash
# 1. 手工 enqueue retention_purge 任务
docker exec restock-dev-backend python -c "
...
"

# 2. 等 5-10s 让 worker 消费，再看 worker 日志
docker logs restock-dev-worker --since 1m 2>&1 | grep -E "retention_purge|deleted|purged|stuck"
```

改为：

```bash
# 1. 手工 enqueue retention_purge 任务
docker compose $COMPOSE_FILES exec -T backend python -c "
...
"

# 2. 等 5-10s 让 worker 消费，再看 worker 日志
docker compose $COMPOSE_FILES logs worker --since 1m 2>&1 | grep -E "retention_purge|deleted|purged|stuck"
```

（`docker compose exec -T` 加 `-T` 禁用 TTY 分配，适合脚本管道；docker exec 默认就没 TTY 所以不需要，但 compose exec 默认有。）

- [ ] **Step 4: 改 §8.2 命令块（4 条 curl）**

Edit `docs/runbook.md:675-689`：

把 4 处 `http://localhost:8088` 替换为 `$API_HOST`：

```bash
# 1. 先把 dashboard snapshot 刷成 ready 状态
curl -X POST $API_HOST/api/metrics/dashboard/refresh \
  -H "Authorization: Bearer <token>" | jq .

# 2. GET dashboard 看 snapshot_status 应为 ready
curl $API_HOST/api/metrics/dashboard -H "Authorization: Bearer <token>" | jq '.snapshot_status, .snapshot_updated_at'

# 3. 改一个敏感字段
curl -X PATCH $API_HOST/api/config/global \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"buffer_days": 31}'

# 4. 再 GET dashboard
curl $API_HOST/api/metrics/dashboard -H "Authorization: Bearer <token>" | jq '.snapshot_status, .snapshot_task_id'
```

同时把 `<dev_token>` 替换为 `<token>`（泛化，因为 prod 的 token 不叫 dev_token）。

- [ ] **Step 5: 改 §8.3 命令块**

Edit `docs/runbook.md:709`：

当前：

```bash
docker exec restock-dev-backend python -c "
...
"
```

改为：

```bash
docker compose $COMPOSE_FILES exec -T backend python -c "
...
"
```

- [ ] **Step 6: 验证没有残留 `restock-dev-*` / `localhost:8088` 在 §8 下**

```bash
awk '/^## 8\. / { p=1 } /^## 9\. / { p=0 } p' /e/Ai_project/restock_system/docs/runbook.md | grep -nE "restock-dev-(backend|worker|scheduler)|localhost:8088" | head
```

Expected: 0 hits。

注意：§2.x 的章节（line 220 等）有"本地 dev 默认容器名固定为 restock-dev-*"的介绍性描述 —— **保留不动**，那是文档说明，不是可复制的命令。

- [ ] **Step 7: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/runbook.md
git -C /e/Ai_project/restock_system commit -m "docs(runbook): §8 部署后验证 SOP 改为 compose-agnostic 命令

CodeRabbit 🟠 Major (PR #13 review #5)：§8 章节标题面向'部署后'，但命令
用 dev 专有的 restock-dev-* 容器名和 localhost:8088。ops 在 prod 复制
会 fail。

新增 §8.0 命令约定：要求操作者先 export COMPOSE_FILES + API_HOST（dev /
prod 两套示例），下面所有命令用 docker compose \$COMPOSE_FILES exec -T
<service> + \$API_HOST/api/... 形式。忘 export 直接跑 fail 是刻意的 ——
强制操作者想清楚环境。

§2.x 介绍性的'dev 容器名固定为 restock-dev-*'描述保留不动（那是文档说明，
不是可复制命令）。"
```

---

### Fix-6 (CodeRabbit #8): frontend-ux findings 计数自洽 + A-1 严重度修正

**Why:** CodeRabbit 🟡 Minor — findings doc header 说 "Critical: 1 / Important: 5 / Minor: 4 / Ack: 2 = 12 条"，但实际 narrative 有 17 条 section headers 和不同分布；汇总表里 A-1 标为 Minor 但 narrative 里 A-1 是 Important。优先级决策文档自洽很重要。

**Files:**
- Modify: `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md`

真实计数（从 narrative 段落 header 统计）：
- Critical: 1（E-1）
- Important: 7（A-1, B-1, B-2, D-1, D-2, F-1, F-3）
- Minor: 6（A-3, B-3, C-1, D-3, E-3, F-2 —— 注意 D-3 narrative 标 Minor 但汇总表里原来也写 Ack，要 re-read 确认）
- Ack: 3（A-2, C-2, E-2）
- 总 17

- [ ] **Step 1: 重读所有 section headers 锁定分布**

```bash
grep -nE "^### [A-Z]-[0-9]+ — .+\[(Critical|Important|Minor|Ack)\]" /e/Ai_project/restock_system/docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md
```

记录准确分类（17 条的每条严重度）。若 D-3 narrative 是 Minor，则 Minor=6 / Ack=3；若 narrative 也写 Ack，则相应调整。

Expected pattern（~17 lines，form：`### X-N — 描述 [严重度]`）。

- [ ] **Step 2: 更新 header 行（line 6）**

Edit `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md:6`。

当前：
```markdown
> **问题总数：** 12 条 / Critical: 1 / Important: 5 / Minor: 4 / Ack: 2
```

改为（按 Step 1 统计的真实数字）：
```markdown
> **问题总数：** 17 条 / Critical: 1 / Important: 7 / Minor: 6 / Ack: 3
```

（如 Step 1 统计与此不符，以 Step 1 为准。）

- [ ] **Step 3: 修 A-1 汇总表行（~line 209）**

Edit `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md:209` 附近。

当前汇总表里 A-1 的行：
```markdown
| A-1 | Minor | main.ts | unhandledrejection 静默吞错 | S |
```

改为（与 narrative line 23 `### A-1 ... [Important]` 一致）：
```markdown
| A-1 | Important | main.ts | unhandledrejection 静默吞错 | S |
```

同时**移到 Important 分组内**（汇总表按严重度分组排序，现有 Important 块在 Critical 后、Minor 前；A-1 原排在 Minor 组，要移到 Important 组尾或按字母顺序插入）。

- [ ] **Step 4: 补 3 条 Ack 行（A-2, C-2, E-2）**

在汇总表末尾（当前最后一行是 `D-3 | Ack`）之后或附近，补齐另 3 条 Ack narrative 对应的行。查 narrative 里 A-2, C-2, E-2 的一句话描述：

```bash
grep -A 1 "^### A-2\|^### C-2\|^### E-2" /e/Ai_project/restock_system/docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md | head
```

以这些 narrative 的 title + 首句为汇总行源，补到汇总表里（模块栏按 narrative 标签填：A-2 是 main.ts/errorHandler，C-2 是 AppLayout 等，E-2 是 SuggestionListView）。

示例新增行格式：
```markdown
| A-2 | Ack | main.ts | errorHandler 已配置但提示文案过于泛化 | 0 |
| C-2 | Ack | 多视图 | 所有表单 Loading 防重复提交覆盖完整 | 0 |
| E-2 | Ack | SuggestionListView | loading 时 empty 态和 loading 态隔离正确 | 0 |
```

**工作量栏 "0" 表示 Ack 无需工作。**

- [ ] **Step 5: 验证计数**

```bash
# 汇总表的行数（排除表头/分隔符）
awk '/^## 汇总表/,/^## / { if (/^\| [A-Z]-/) print }' /e/Ai_project/restock_system/docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md | wc -l

# 各严重度分布
awk '/^## 汇总表/,/^## / { if (/^\| [A-Z]-/) print }' /e/Ai_project/restock_system/docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md | awk -F'|' '{print $3}' | sort | uniq -c
```

Expected: 总 17 行，分布与 Step 1 统计一致。

- [ ] **Step 6: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md
git -C /e/Ai_project/restock_system commit -m "docs(review): frontend-ux findings 计数自洽 + A-1 严重度修正

CodeRabbit 🟡 Minor (PR #13 review #8)：
- Header 计数从 '12 条 Critical:1 Important:5 Minor:4 Ack:2' 改为真实
  17 条 / Critical:1 / Important:7 / Minor:6 / Ack:3
- A-1 (unhandledrejection) narrative 标 Important 但汇总表标 Minor —
  以 narrative 为准，汇总表改 Important + 移到 Important 分组
- 补齐汇总表缺失的 3 条 Ack 行（A-2 / C-2 / E-2）

优先级决策文档自洽，避免未来 follow-up plan 取数据时数字对不上。"
```

---

## Phase C — 验证 + PR 续推

### Fix-7: 全量回归 + push

- [ ] **Step 1: mypy + ruff**

```bash
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /app && MYPY_CACHE_DIR=/tmp/.mypy_cache /install/bin/mypy app 2>&1 | tail -3"
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "/install/bin/ruff check /app/app --cache-dir /tmp/.ruff_cache 2>&1 | tail -3"
```

Expected:
- mypy: `Success: no issues found in 109 source files`
- ruff: `All checks passed!`

- [ ] **Step 2: pytest 分片**

```bash
MSYS_NO_PATHCONV=1 docker exec --user root restock-dev-backend rm -rf /tmp/tests/tests
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)" restock-dev-backend:/tmp/
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages python -m pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests/unit -n auto -q --no-header 2>&1 | tail -3"
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages python -m pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests/integration -q --no-header 2>&1 | tail -3"
```

Expected:
- unit: `~346 passed in ~6s`（+1 from Fix-1）
- integration: `33 passed in ~75s`

- [ ] **Step 3: frontend 快检**

```bash
cd /e/Ai_project/restock_system/frontend && npx vue-tsc --noEmit 2>&1 | tail -3 && npm run lint 2>&1 | tail -3
```

Expected: 无 error。

（Frontend 无改动，但为保险起见。）

- [ ] **Step 4: Push + 让 CodeRabbit 再 review**

```bash
git -C /e/Ai_project/restock_system push 2>&1 | tail -3
gh pr comment 13 --body "已按 CodeRabbit 建议补修 6 条 actionable 中的 5 条（#1 #2 #3 #4 #8）+ 升级 #5 为 FIX NOW 也已修。未动 #6（markdownlint 不在 CI，declined）和 #7（DR findings path 前缀，归档到未来 docs 迁移）。请 incremental review。

@coderabbitai review"
```

- [ ] **Step 5: 等 CI + CodeRabbit 再跑一轮**

```bash
sleep 60  # 或用 monitor / gh pr checks 13 --watch
gh pr view 13 --json state,mergeable,mergeStateStatus,statusCheckRollup --jq '{mergeable, mergeStateStatus, checks: [.statusCheckRollup[] | {name, conclusion, state}]}'
```

Expected：
- mergeable: `MERGEABLE` / mergeStateStatus: `CLEAN`
- backend / frontend / docker-build / CodeRabbit: all SUCCESS

如果 CodeRabbit 再留 comment，按同样 triage 流程决定修/deferred。

- [ ] **Step 6: Merge**

```bash
gh pr merge 13 --merge --delete-branch
```

Expected: MERGED; feat/post-audit-round-2 branch 删除（local + remote）。

---

## 自检 Checklist

- [x] 每个 Task 有明确文件路径 + 完整代码块 + 运行命令
- [x] 每个 Step 粒度 2-5 分钟
- [x] 无 "TBD" / "implement later" 占位（`<填写负责人姓名或团队别名>` 是 **产物里** 的占位符，要求用户部署前填；不是 plan 的未完成项）
- [x] 类型一致性：`retention_stuck_generating_hours` 贯穿 Fix-1；`exported_at` / `generation_status` 贯穿 Fix-2
- [x] Fix-1 / Fix-2 走 TDD（先测试失败 → 实现 → 测试通过 → commit）；其余文档 / shell 改动是 localized edit + verify
- [x] Phase C 含完整回归 + PR push + 等 review + merge 的闭环

## Spec 覆盖

- Fix-1 ← CodeRabbit #1（config.py 负值校验）
- Fix-2 ← CodeRabbit #2（test 补 exported_at 断言）
- Fix-3 ← CodeRabbit #3（restore_db.sh echo 引号）
- Fix-4 ← CodeRabbit #4（runbook .env 命名 + 占位符）
- Fix-5 ← CodeRabbit #5（runbook §8 compose-agnostic）
- Fix-6 ← CodeRabbit #8（frontend-ux findings 计数自洽）
- Fix-7 ← Phase C 收尾（回归 + push + merge）

已覆盖用户明确要求的 6 条。

跳过 #6（markdownlint plan 文档，declined — 不在 CI）+ #7（DR findings path 前缀 bug，归档到未来 docs 迁移）。

## 风险记录

- **Fix-5 Step 2 引入 `COMPOSE_FILES` 环境变量**：操作者必须 export 才能跑。若直接 copy-paste 会 fail — 刻意设计（见 commit message 里"强制操作者想清楚环境"）。
- **Fix-6 Step 1 的 narrative 统计若与我预估不同**：以 Step 1 实际 grep 结果为准调整 header 和汇总表。
- **Fix-7 Step 5 CodeRabbit 二次 review 可能再留 comment**：视严重度 triage，绝大概率是更 minor 的细节，不阻塞 merge。
