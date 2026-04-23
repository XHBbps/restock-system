# Post-Audit Round 2: Polish + New-Domain Audits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 延续 2026-04-21 audit 清理扫尾：7 个"值得做 / 可做可不做"的工程改进（tripwire 测试、stuck generating 兜底、运维 runbook、engine type aliases、sync 覆盖率、dependabot 清理、CI 分片），然后对 3 个从未被 audit 覆盖的领域（业务正确性 / 灾备演练 / 前端 UX）做聚焦审查产出 findings 文档。

**Architecture:**
- **Phase 1**（Task 1-3, 🟢 高价值实施）：关闭 audit 残余的"小坑位"— Dashboard stale 敏感字段 tripwire 测试 + `suggestion_snapshot.generation_status='generating'` 超时清理 + retention / stale / 410 的 runbook 手测 SOP。
- **Phase 2**（Task 4-7, 🟡 工程卫生）：低风险局部改善 — engine outer dict 的 type alias 命名 + `sync.shop` / `sync.warehouse` 加单测 + 9 个 dependabot PR 分类处理 + pytest-xdist 把 CI 从 10 min 缩到 ~4 min。
- **Phase 3**（Task 9-11, 🔵 新领域审查）：三个独立 research subagent 分别负责**业务正确性**（step1-6 公式边界 + 时区 / 空集合 / 幂等性）、**灾备演练**（rollback + pg_backup restore + worker 假死）、**前端 UX**（错误边界 / loading / 表单禁用 / 键盘）产出 `docs/superpowers/reviews/2026-04-23-<domain>-findings.md`。每份 findings 列出**不需动作的清单**（ack 后续可能回头）和**建议的 follow-up plan**（如有 Critical）。

**Tech Stack:** Python 3.11 + pytest + SQLAlchemy 2.0（引擎 / retention 改动）；Vue 3 + TypeScript + Vitest（前端审查）；pytest-xdist（并行测试）；GitHub Actions + gh CLI（dependabot 批处理）；docker compose dev stack（手测 SOP 验证）。

**Pre-flight:**
- 从 master 新开分支：`git -C /e/Ai_project/restock_system checkout -b feat/post-audit-round-2`
- 确认 master 干净且 audit round-1 / round-2 已合入（commit `630ffed` Merge PR #12 在 master）
- dev 容器 healthy：`docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev ps` 应见 6 个 healthy
- pytest baseline 应为 **362 passed / 0 failed**

---

## 文件结构全景

**Phase 1 (Task 1-3):**
- Modify: `backend/app/api/config.py`（暴露 `GLOBAL_CONFIG_SENSITIVE_FIELDS` / `GLOBAL_CONFIG_NEUTRAL_FIELDS` 常量供 tripwire 使用）
- Modify: `backend/app/tasks/jobs/retention.py`（加 `purge_stuck_generating` 第 4 子函数）
- Modify: `backend/app/config.py`（加 `retention_stuck_generating_hours: int = 1`）
- Modify: `docs/runbook.md`（新增 "Post-deploy verification" 小节）
- Test (new): `backend/tests/unit/test_config_sensitive_fields_tripwire.py`
- Test (modify): `backend/tests/unit/test_retention_job.py`（+3 条 purge_stuck_generating 断言）

**Phase 2 (Task 4-7):**
- Modify: `backend/app/engine/context.py`（加 `VelocityMap` / `SaleDaysMap` / `CountryQtyMap` type aliases）
- Modify: `backend/app/engine/step1_velocity.py` / `step2_sale_days.py` / `step3_country_qty.py` / `step4_total.py` / `step6_timing.py` / `runner.py` / `api/metrics.py`（把裸 `dict[str, dict[str, float]]` 签名替换为 alias）
- Test (new): `backend/tests/unit/test_sync_shop.py`
- Test (new): `backend/tests/unit/test_sync_warehouse.py`
- Modify: `backend/pyproject.toml`（加 `pytest-xdist` 到 `[tool.poetry.group.dev.dependencies]` 或等价）
- Modify: `.github/workflows/ci.yml`（pytest 命令加 `-n auto`）
- Runbook action (non-code): 9 个 open dependabot PRs 批处理（merge / close）

**Phase 3 (Task 9-11, research only, produces docs):**
- New: `docs/superpowers/reviews/2026-04-23-business-correctness-findings.md`
- New: `docs/superpowers/reviews/2026-04-23-disaster-recovery-findings.md`
- New: `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md`
- 无代码改动（纯 audit，发现 Critical 才回来改）

---

## Phase 1 — 高价值实施

### Task 1: Dashboard stale 敏感字段 tripwire 测试

**Why:** `_DASHBOARD_SENSITIVE_FIELDS` 是 6 项硬编码 frozenset（`restock_regions` / `eu_countries` / `target_days` / `lead_time_days` / `buffer_days` / `safety_stock_days`）。未来给 `global_config` 加新字段（如"最小起订量"），新开发者不知道该不该加入这个集合 — 漏加 → 用户改了值但 dashboard 不 refresh。Tripwire 测试：用 SQLAlchemy 内省拿出所有 GlobalConfig 物料字段，必须每个都在"敏感"或"中性"白名单里，新字段加入 model 不分类即测试红。

**Files:**
- Modify: `backend/app/api/config.py`
- Test: `backend/tests/unit/test_config_sensitive_fields_tripwire.py` (new)

- [ ] **Step 1: 暴露中性字段白名单常量**

Edit `backend/app/api/config.py` — find the `_DASHBOARD_SENSITIVE_FIELDS = frozenset({...})` block (introduced by audit round-1 commit `533040b`). Rename to public and add a sibling `GLOBAL_CONFIG_NEUTRAL_FIELDS`:

```python
# 改动以下任一字段即把 dashboard_snapshot.stale 置 TRUE，下次 dashboard API
# 自动 enqueue 刷新。
GLOBAL_CONFIG_SENSITIVE_FIELDS = frozenset(
    {
        "restock_regions",
        "eu_countries",
        "target_days",
        "lead_time_days",
        "buffer_days",
        "safety_stock_days",
    }
)

# 与 dashboard 展示无关、变更无需 stale 的字段。新增 GlobalConfig 字段
# 必须在 SENSITIVE 或 NEUTRAL 任一集合中声明，否则 tripwire 测试会红。
GLOBAL_CONFIG_NEUTRAL_FIELDS = frozenset(
    {
        "id",
        "sync_interval_minutes",  # 调度触发频率，不影响 dashboard 数据
        "scheduler_enabled",
        "shop_sync_mode",
        "login_password_hash",
        "suggestion_generation_enabled",
        "generation_toggle_updated_by",
        "generation_toggle_updated_at",
        "created_at",
        "updated_at",
    }
)
```

Then update the existing reference in `patch_global` from `_DASHBOARD_SENSITIVE_FIELDS` to `GLOBAL_CONFIG_SENSITIVE_FIELDS`:

Find this block inside `patch_global`:

```python
        sensitive_updates = _DASHBOARD_SENSITIVE_FIELDS & updates.keys()
        sensitive_old = {f: getattr(row, f, None) for f in sensitive_updates}
```

Change to:

```python
        sensitive_updates = GLOBAL_CONFIG_SENSITIVE_FIELDS & updates.keys()
        sensitive_old = {f: getattr(row, f, None) for f in sensitive_updates}
```

Delete the old `_DASHBOARD_SENSITIVE_FIELDS` definition (it's been replaced).

- [ ] **Step 2: 写 tripwire 失败测试**

Create `backend/tests/unit/test_config_sensitive_fields_tripwire.py`:

```python
"""Tripwire：GlobalConfig 所有列必须被分类为 SENSITIVE 或 NEUTRAL。

新增字段时如果忘记分类，此测试会红，迫使开发者想清楚：
- 改这个值需要 dashboard refresh 吗？→ 加入 SENSITIVE
- 纯运行时配置 / 审计字段？→ 加入 NEUTRAL
"""

from __future__ import annotations

from app.api.config import (
    GLOBAL_CONFIG_NEUTRAL_FIELDS,
    GLOBAL_CONFIG_SENSITIVE_FIELDS,
)
from app.models.global_config import GlobalConfig


def test_every_global_config_column_is_classified() -> None:
    all_mapped_columns = {col.key for col in GlobalConfig.__table__.columns}
    classified = GLOBAL_CONFIG_SENSITIVE_FIELDS | GLOBAL_CONFIG_NEUTRAL_FIELDS

    unclassified = all_mapped_columns - classified
    assert not unclassified, (
        f"GlobalConfig 新增了未分类字段 {unclassified}。请决定：\n"
        f"  - 改此字段是否应触发 dashboard_snapshot.stale=True？\n"
        f"    是 → 加入 GLOBAL_CONFIG_SENSITIVE_FIELDS\n"
        f"    否 → 加入 GLOBAL_CONFIG_NEUTRAL_FIELDS"
    )


def test_no_field_is_classified_twice() -> None:
    overlap = GLOBAL_CONFIG_SENSITIVE_FIELDS & GLOBAL_CONFIG_NEUTRAL_FIELDS
    assert not overlap, f"字段同时出现在 SENSITIVE 和 NEUTRAL：{overlap}"


def test_classified_fields_all_exist_on_model() -> None:
    all_mapped_columns = {col.key for col in GlobalConfig.__table__.columns}
    classified = GLOBAL_CONFIG_SENSITIVE_FIELDS | GLOBAL_CONFIG_NEUTRAL_FIELDS

    stale_classifications = classified - all_mapped_columns
    assert not stale_classifications, (
        f"SENSITIVE/NEUTRAL 列表里有 model 上已不存在的字段："
        f"{stale_classifications}。请清理过时分类。"
    )
```

- [ ] **Step 3: 跑测试确认失败 → 通过**

Copy changed files into container + run tests:

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/app && pwd -W)/api/config.py" restock-dev-backend:/app/app/api/config.py
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)/unit/test_config_sensitive_fields_tripwire.py" restock-dev-backend:/tmp/tests/unit/test_config_sensitive_fields_tripwire.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_config_sensitive_fields_tripwire.py -v --no-header 2>&1"
```

Expected: 3 passed.

Also re-run existing config_api test:

```bash
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/integration/test_config_api.py -v --no-header 2>&1 | tail -15"
```

Expected: 8 passed（前 5 个原有 + 3 个 audit round-1 加的 stale 测试）；重命名 `_DASHBOARD_SENSITIVE_FIELDS` → `GLOBAL_CONFIG_SENSITIVE_FIELDS` 应不影响任何测试。

- [ ] **Step 4: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/app/api/config.py backend/tests/unit/test_config_sensitive_fields_tripwire.py
git -C /e/Ai_project/restock_system commit -m "test(backend): GlobalConfig 字段分类 tripwire + 常量改公开导出

把 _DASHBOARD_SENSITIVE_FIELDS 改名为 GLOBAL_CONFIG_SENSITIVE_FIELDS（公开），
新增 GLOBAL_CONFIG_NEUTRAL_FIELDS 集合声明"与 dashboard 无关的字段"；
加 3 条 tripwire 测试：
- 所有物料字段必须在 SENSITIVE ∪ NEUTRAL（未分类会红）
- 两集合不能交叉
- 集合里不能有 model 上已删的字段

这样未来给 GlobalConfig 加字段时，新开发者必须做出"这个字段改了要不要
refresh dashboard？"的显式决策，防止漏加导致 UI 过时。"
```

---

### Task 2: `suggestion_snapshot.generation_status='generating'` 超时清理

**Why:** 目前 snapshot 生成中若进程被 kill / OOM，DB 里可能留一条永远 `generating` 的行。用户再点"导出"会产生新 version（绕过旧行），但前端 snapshot list 会看到 generating + ready 两条，产生视觉噪音。加一个 retention 扩展：超过 N 小时（默认 1 小时）还是 generating 的 snapshot 视为"卡死"，标 `failed` + 写 `generation_error='stuck in generating > Nh'`。

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/tasks/jobs/retention.py`
- Test: `backend/tests/unit/test_retention_job.py`（append）

- [ ] **Step 1: 加 Settings env**

Edit `backend/app/config.py` — find the `Retention 保留天数` block and add below the 3 existing fields:

```python
    # Retention 保留天数（04:00 daily cron 依据，0 表示永不过期）
    retention_task_run_days: int = 90
    retention_inventory_history_days: int = 180
    retention_exports_days: int = 60
    # suggestion_snapshot.generation_status='generating' 超过 N 小时视为卡死
    # （进程崩 / OOM 场景），被 retention_purge_job 标 failed。0 表示禁用。
    retention_stuck_generating_hours: int = 1
```

- [ ] **Step 2: 写 purge_stuck_generating 失败测试**

Append to `backend/tests/unit/test_retention_job.py` (after the 12 existing tests):

```python
# --------- purge_stuck_generating ---------

@pytest.mark.asyncio
async def test_purge_stuck_generating_returns_zero_when_hours_zero() -> None:
    from app.tasks.jobs.retention import purge_stuck_generating

    db = _FakeDb([])
    result = await purge_stuck_generating(db, hours=0)
    assert result == 0
    assert db.executed == []


@pytest.mark.asyncio
async def test_purge_stuck_generating_marks_rows_failed() -> None:
    from app.tasks.jobs.retention import purge_stuck_generating

    db = _FakeDb([_RowcountResult(3)])
    result = await purge_stuck_generating(db, hours=1)
    assert result == 3
    # 只执行了 1 条 UPDATE 语句
    assert len(db.executed) == 1
    # SQL 含 generation_status='generating' + 时间阈值
    compiled = str(db.executed[0])
    assert "generation_status" in compiled.lower()


@pytest.mark.asyncio
async def test_purge_stuck_generating_handles_null_rowcount() -> None:
    from app.tasks.jobs.retention import purge_stuck_generating

    db = _FakeDb([_RowcountResult(None)])  # type: ignore[arg-type]
    result = await purge_stuck_generating(db, hours=1)
    assert result == 0
```

- [ ] **Step 3: 运行测试确认失败**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)/unit/test_retention_job.py" restock-dev-backend:/tmp/tests/unit/test_retention_job.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_retention_job.py -v --no-header 2>&1 | tail -10"
```

Expected: 3 new tests fail with `ImportError: cannot import name 'purge_stuck_generating'`.

- [ ] **Step 4: 实现 purge_stuck_generating**

Edit `backend/app/tasks/jobs/retention.py`:

4.1 — Add import at the top imports block:

```python
from app.models.suggestion_snapshot import SuggestionSnapshot
```

4.2 — Add the function right after `purge_exports` (before `retention_purge_job`):

```python
async def purge_stuck_generating(db: AsyncSession, hours: int) -> int:
    """把卡在 generation_status='generating' 超过 N 小时的 snapshot 标 failed。

    进程崩 / OOM / worker 被 docker stop 会留下永远 generating 的 snapshot，
    本函数提供兜底清理。
    """
    if hours <= 0:
        return 0
    cutoff = now_beijing() - timedelta(hours=hours)
    result = await db.execute(
        update(SuggestionSnapshot)
        .where(SuggestionSnapshot.generation_status == "generating")
        .where(SuggestionSnapshot.exported_at < cutoff)
        .values(
            generation_status="failed",
            generation_error=f"stuck in generating > {hours}h, cleaned by retention",
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
```

4.3 — Register the call in `retention_purge_job`. Find the end of the existing job body (after `purged_exports = await purge_exports(...)` block) and add a fourth block before the final `await ctx.progress(current_step="完成", ...)`:

```python
    async with async_session_factory() as db:
        stuck_failed = await purge_stuck_generating(
            db, settings.retention_stuck_generating_hours
        )
        await db.commit()
    logger.info("retention_purge_stuck_generating", failed=stuck_failed)
```

And update the final progress call to include this count:

```python
    await ctx.progress(
        current_step="完成",
        step_detail=(
            f"task_run {deleted_task} / inventory_history {deleted_inv} / "
            f"exports {purged_exports} / stuck_generating {stuck_failed}"
        ),
    )
```

4.4 — Update module docstring (top of file) to list 4 retention actions instead of 3. Find the 三连 section and add a 4th bullet:

```
- `purge_stuck_generating`：suggestion_snapshot.generation_status='generating'
  且 exported_at 超过 retention_stuck_generating_hours（默认 1h）的行标 failed，
  兜底 OOM / crash / kill 场景。
```

- [ ] **Step 5: 运行测试确认通过**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/app && pwd -W)/tasks/jobs/retention.py" restock-dev-backend:/app/app/tasks/jobs/retention.py
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/app && pwd -W)/config.py" restock-dev-backend:/app/app/config.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_retention_job.py -v --no-header 2>&1 | tail -20"
```

Expected: 15 passed (12 existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/app/config.py backend/app/tasks/jobs/retention.py backend/tests/unit/test_retention_job.py
git -C /e/Ai_project/restock_system commit -m "feat(backend): retention 加 purge_stuck_generating 兜底 OOM/crash

suggestion_snapshot.generation_status='generating' 且 exported_at 超过
retention_stuck_generating_hours (默认 1h) 的行标为 failed + 写
generation_error。场景：worker 进程在 workbook.save 后 commit 前被
kill / OOM，留下永远 generating 的 snapshot 行 — 前端 snapshot list
会显示 generating + ready 双条，产生视觉噪音。

retention_purge_job 扩展为 4 连（task_run / inventory_history /
exports / stuck_generating）；Settings 加 RETENTION_STUCK_GENERATING_HOURS
env 控制（0 = 禁用）。

3 条单测：days=0 短路 / rowcount 正常返回 / rowcount=None 兜底。"
```

---

### Task 3: PR #11 未勾选 3 条人工手测 runbook

**Why:** PR #11 test plan 有 3 条 "[ ] 人工手测"（retention job / dashboard stale 自动失效 / 410 purged 前端提示）未勾选。功能逻辑已有 integration 测覆盖，但 E2E 在真 docker 容器里跑一遍能发现集成层问题（cron 是否真注册 / worker 是否真消费任务 / 前端 axios blob 错误解包是否真工作）。把这 3 条写成 runbook SOP，首次 deploy 或每季度演练执行一次。

**Files:**
- Modify: `docs/runbook.md`

- [ ] **Step 1: 找 runbook 结构**

Read `docs/runbook.md` 顶部 50 行了解章节命名惯例（e.g. `## 1. 回滚` / `## 2. 备份恢复` 这种）。

- [ ] **Step 2: 加 "部署后验证" 章节**

Edit `docs/runbook.md` — append a new section at the end (maintain the same heading depth as sibling sections):

````markdown
## 部署后验证（retention / dashboard stale / 410 Gone）

> 首次部署或每季度演练一次。每条都是独立可跑，互不依赖。

### P-1: Retention purge 手工触发

验证：04:00 cron 对应的 retention_purge 任务能被 worker 正确消费，三连（task_run / inventory_history / exports）+ stuck_generating 的日志都正确写入。

```bash
# 1. 手工 enqueue retention_purge 任务（dedupe_key=retention_purge 保证不重复）
docker exec restock-dev-backend python -c "
import asyncio
from app.db.session import async_session_factory
from app.tasks.queue import enqueue_task

async def main():
    async with async_session_factory() as db:
        task_id, existing = await enqueue_task(
            db, job_name='retention_purge', trigger_source='manual',
            dedupe_key='retention_purge', payload={'triggered_by': 'post_deploy_verify'}
        )
        print(f'task_id={task_id} existing={existing}')

asyncio.run(main())
"

# 2. 等 5-10s 让 worker 消费，再看 worker 日志（dev 容器用 structlog JSON）
docker logs restock-dev-worker --since 1m 2>&1 | grep -E "retention_purge|deleted|purged|stuck"
```

**预期**：日志按顺序出现 `retention_purge_task_run deleted=N` / `retention_purge_inventory_history deleted=N` / `retention_purge_exports purged=N` / `retention_purge_stuck_generating failed=N`。首次 deploy 时 N 大概率都是 0。

**可能的异常**：
- 若日志完全没出现 `retention_purge_*`：worker 没消费，检查 `app.tasks.jobs` 导入是否包含 `retention`（应在 `backend/app/main.py:42` 有 `from app.tasks.jobs import retention as _job_retention`）。
- 若某行 `deleted=N` 中 N > 100：磁盘数据可能超预期旧，检查 env 的 `RETENTION_*_DAYS` 是否设反了。

### P-2: Dashboard stale 自动失效 → 自动 refresh

验证：`patch_global` 改敏感字段后，下次 GET /api/metrics/dashboard 自动入队刷新。

```bash
# 1. 先把 dashboard snapshot 刷成 ready 状态
curl -X POST http://localhost:8088/api/metrics/dashboard/refresh \
  -H "Authorization: Bearer <dev_token>" | jq .
# 等 task_id 返回 → 等 10s worker 跑完

# 2. GET dashboard 看 snapshot_status 应为 ready，记住 snapshot_updated_at
curl http://localhost:8088/api/metrics/dashboard -H "Authorization: Bearer <dev_token>" | jq '.snapshot_status, .snapshot_updated_at'

# 3. 改一个敏感字段（e.g. buffer_days 从 30 → 31）
curl -X PATCH http://localhost:8088/api/config/global \
  -H "Authorization: Bearer <dev_token>" \
  -H "Content-Type: application/json" \
  -d '{"buffer_days": 31}'

# 4. 再 GET dashboard — 应该看到 snapshot_status=refreshing + snapshot_task_id 非空
curl http://localhost:8088/api/metrics/dashboard -H "Authorization: Bearer <dev_token>" | jq '.snapshot_status, .snapshot_task_id'

# 5. 等 10s worker 跑完刷新，再 GET — 应回到 ready，snapshot_updated_at 更新
```

**预期**：步骤 4 返回 `refreshing` + 有 task_id；步骤 5 返回 `ready` + updated_at 比步骤 2 大。

**可能的异常**：
- 步骤 4 仍返回 `ready`：`GLOBAL_CONFIG_SENSITIVE_FIELDS`（见 `backend/app/api/config.py`）没正确检测到 `buffer_days`，或 `dashboard_snapshot.stale` 字段迁移没到。
- 步骤 5 一直 `refreshing`：worker 没消费 `refresh_dashboard_snapshot` 任务，检查 worker 日志。

### P-3: Excel 文件 purged 后前端下载 410 提示

验证：retention 清理磁盘 Excel 并写 `excel_export_log.file_purged_at` 后，前端下载端显示"已过期清理"友好提示。

```bash
# 1. 导出一个 procurement snapshot（前端 / 或 curl），记下 snapshot_id
# 前端 → 建议单列表 → 选中 item → 导出采购单

# 2. 模拟 retention 清理（开发环境快速路径）：手工删磁盘 + 标记 log
docker exec restock-dev-backend python -c "
import asyncio
from datetime import datetime
from pathlib import Path
from sqlalchemy import update, select
from app.config import get_settings
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.excel_export_log import ExcelExportLog
from app.models.suggestion_snapshot import SuggestionSnapshot

SNAPSHOT_ID = <填刚才导出的 snapshot_id>

async def main():
    async with async_session_factory() as db:
        snap = (await db.execute(
            select(SuggestionSnapshot).where(SuggestionSnapshot.id == SNAPSHOT_ID)
        )).scalar_one()
        root = Path(get_settings().export_storage_dir).resolve()
        path = root / (snap.file_path or '')
        if path.exists():
            path.unlink()
            print(f'Deleted {path}')
        await db.execute(
            update(ExcelExportLog)
            .where(ExcelExportLog.snapshot_id == SNAPSHOT_ID)
            .where(ExcelExportLog.action == 'generate')
            .values(file_purged_at=now_beijing())
        )
        await db.commit()

asyncio.run(main())
"

# 3. 前端打开 /restock/history → 详情 → 版本列表 → 点刚才的版本的"下载"按钮
```

**预期**：前端弹红色 ElMessage "该版本已过期清理（保留期 60 天）"（文字含 `RETENTION_EXPORTS_DAYS` env 值）。

**可能的异常**：
- 看到通用的 "下载失败" 或后端 detail "文件已丢失"：`_decodeBlobErrorInPlace`（`frontend/src/api/snapshot.ts`）没正常解包 blob 错误，或后端 404→410 逻辑分支错了。
- 看到 500：检查 docker exec python 脚本是否真的写入了 `file_purged_at`（用 `psql -c "SELECT file_purged_at FROM excel_export_log WHERE snapshot_id = ..."` 复核）。
````

- [ ] **Step 3: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/runbook.md
git -C /e/Ai_project/restock_system commit -m "docs(runbook): 加部署后验证 SOP（retention / stale / 410 Gone）

关闭 PR #11 test plan 里未勾选的 3 条人工手测，转成 runbook 常驻 SOP：
首次部署或每季度演练一次。每条含原因、完整 docker exec 命令、预期输出、
异常排查指引。"
```

---

## Phase 2 — 工程卫生

### Task 4: Engine outer dict 加 type alias 改善可读性

**Why:** Audit round-2 的 P2-A4 只把**内层命名 dict**（`{available, reserved, in_transit, total}`）dataclass 化。外层 `dict[str, dict[str, float]]` 等 2D lookup 保留 dict 是正确的（无 dataclass 收益），但**签名可读性差** — 读者看到 `dict[str, dict[str, float]]` 不知道这是 `sku → country → velocity` 还是其他含义。加 `VelocityMap` / `SaleDaysMap` / `CountryQtyMap` 三个 TypeAlias，签名自解释。零行为变化。

**Files:**
- Modify: `backend/app/engine/context.py`
- Modify: `backend/app/engine/step1_velocity.py` / `step2_sale_days.py` / `step3_country_qty.py` / `step4_total.py` / `step6_timing.py` / `runner.py`
- Modify: `backend/app/api/metrics.py`（consumer）

- [ ] **Step 1: 在 context.py 加 type aliases**

Edit `backend/app/engine/context.py` — at the top of the file (after imports, before `InventoryStock`), add:

```python
# 外层 dict[sku][country] 2D lookup 的 TypeAlias，签名可读性用。
# 不做 dataclass 是因为它是纯 lookup 没方法/派生属性，dataclass 无收益。
VelocityMap = dict[str, dict[str, float]]
SaleDaysMap = dict[str, dict[str, float]]
CountryQtyMap = dict[str, dict[str, int]]
InventoryMap = dict[str, dict[str, "InventoryStock"]]  # forward ref
```

Note: `InventoryMap` uses forward-ref string because `InventoryStock` is defined below. If ruff / mypy flag, use:

```python
from __future__ import annotations  # (should already be there)
...
InventoryMap = dict[str, dict[str, InventoryStock]]
```

- [ ] **Step 2: 在 step 签名使用 alias**

Substitute in each file (sed-style replacement, but do it as Edit tool calls):

**`backend/app/engine/step1_velocity.py`:**
```python
# import line add
from app.engine.context import VelocityMap

# aggregate_velocity_from_items signature
def aggregate_velocity_from_items(
    items: list[tuple[str, str, date, int, int]],
    today: date,
) -> VelocityMap:  # was: dict[str, dict[str, float]]
    ...

# result type annotation
result: defaultdict[str, dict[str, float]] = defaultdict(dict)  # keep this internal

# run_step1 return
async def run_step1(
    db: AsyncSession,
    commodity_skus: list[str] | None,
    today: date,
    allowed_countries: set[str] | None = None,
) -> VelocityMap:  # was: dict[str, dict[str, float]]
    ...
```

**`backend/app/engine/step2_sale_days.py`:**
```python
from app.engine.context import InventoryMap, InventoryStock, SaleDaysMap, VelocityMap

def merge_inventory(
    oversea: dict[tuple[str, str], dict[str, int]],
    in_transit: dict[tuple[str, str], int],
) -> InventoryMap:  # was: dict[str, dict[str, InventoryStock]]
    ...

def compute_sale_days(
    velocity: VelocityMap,  # was: dict[str, dict[str, float]]
    inventory: InventoryMap,
) -> SaleDaysMap:  # was: dict[str, dict[str, float]]
    ...

async def run_step2(
    db: AsyncSession,
    velocity: VelocityMap,
    commodity_skus: list[str] | None,
) -> tuple[SaleDaysMap, InventoryMap]:
    ...
```

**`backend/app/engine/step3_country_qty.py`:**
```python
from app.engine.context import CountryQtyMap, InventoryMap, InventoryStock, VelocityMap

def compute_country_qty(
    velocity: VelocityMap,
    inventory: InventoryMap,
    target_days: int,
) -> CountryQtyMap:
    ...
```

**`backend/app/engine/step4_total.py`:**
```python
from app.engine.context import EngineContext, LocalStock
# No alias changes needed — step4 signatures are per-SKU, not maps

# Only step4_total function's param type is already EngineContext
```

(No alias changes in step4 because signatures operate on per-SKU scalars not maps. Skip this step for step4.)

**`backend/app/engine/step6_timing.py`:**
```python
from app.engine.context import SaleDaysMap

def compute_urgency_for_sku(
    sale_days_by_country: Mapping[str, float | int | None],
    ...
) -> ...:
    ...

# If there's a function signature that takes dict[str, dict[str, float]] as sale_days input
# (e.g. full-table variant), change to SaleDaysMap. Otherwise skip.
```

(Check step6_timing; likely per-SKU Mapping; adjust alias use only where whole-table maps appear.)

**`backend/app/engine/runner.py`:**
```python
# Find local variable annotations for velocity / sale_days / country_qty / inventory:
# Example before:
#   sale_days, inventory = await run_step2(db, velocity, sku_list)
#
# These are inferred from return types, no explicit annotation needed. Just ensure
# run_step2 and others return the alias types (already done above).
# No runner.py changes strictly required, but if any `dict[str, dict[str, ...]]` local
# annotations appear, change to aliases.
```

Actually only annotate where explicit. Scan `runner.py` for `dict[str, dict[str,` and update.

**`backend/app/api/metrics.py`:**
```python
# Same treatment: if build_dashboard_payload / build_country_restock_distribution have
# dict[str, dict[str, ...]] parameter annotations, replace with aliases.
```

- [ ] **Step 3: 运行全量测试确认无回归**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/app && pwd -W)" restock-dev-backend:/app/
MSYS_NO_PATHCONV=1 docker exec --user root restock-dev-backend rm -rf /tmp/tests/tests
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)" restock-dev-backend:/tmp/
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests/unit -q --no-header 2>&1 | tail -5"
```

Expected: `36X passed`. Alias rename is transparent — no behavior change.

- [ ] **Step 4: mypy 确认无回归**

```bash
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /app && MYPY_CACHE_DIR=/tmp/.mypy_cache /install/bin/mypy app 2>&1 | tail -5"
```

Expected: `Success: no issues found in 109 source files`.

- [ ] **Step 5: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/app/engine/context.py backend/app/engine/step1_velocity.py backend/app/engine/step2_sale_days.py backend/app/engine/step3_country_qty.py backend/app/engine/step4_total.py backend/app/engine/step6_timing.py backend/app/engine/runner.py backend/app/api/metrics.py
git -C /e/Ai_project/restock_system commit -m "refactor(engine): 加 VelocityMap / SaleDaysMap / CountryQtyMap / InventoryMap type aliases

外层 dict[sku][country] 是纯 2D lookup，不做 dataclass（无收益），但签名
dict[str, dict[str, float]] 缺语义。引入 TypeAlias 让签名自解释：
- VelocityMap / SaleDaysMap → dict[sku, dict[country, float]]
- CountryQtyMap → dict[sku, dict[country, int]]
- InventoryMap → dict[sku, dict[country, InventoryStock]]

step1-3 / step6 / runner / metrics.build_dashboard_payload 签名同步替换。
零行为变化，纯可读性改进。"
```

---

### Task 5: `sync.shop` / `sync.warehouse` 基础单测

**Why:** CI coverage 显示 `app/sync/shop.py` 34% / `app/sync/warehouse.py` 43%。`_upsert_shop` / `_upsert_warehouse` 是被 integration e2e 覆盖但无聚焦单测的 happy-path 函数。参照 `test_sync_inventory_eu.py` 的 `_FakeDb` 模式补 5 条左右单测，覆盖：快乐路径 / 缺字段 / type 转换 / 空 name 等。

**Files:**
- Test (new): `backend/tests/unit/test_sync_shop.py`
- Test (new): `backend/tests/unit/test_sync_warehouse.py`

- [ ] **Step 1: Read target files + 决定单测范围**

```bash
cat /e/Ai_project/restock_system/backend/app/sync/shop.py
cat /e/Ai_project/restock_system/backend/app/sync/warehouse.py
```

记下 `_upsert_shop` / `_upsert_warehouse` 的分支：
- 早退条件（e.g. `if not shop_id: return`）
- 枚举 / type 转换（e.g. `type_int = int(type_raw) if ... else 0`）
- values dict 构造
- pg_insert + on_conflict_do_update 调用

- [ ] **Step 2: 写 test_sync_shop.py**

Create `backend/tests/unit/test_sync_shop.py`:

```python
"""Unit tests for sync/shop._upsert_shop."""

from __future__ import annotations

from typing import Any

import pytest


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None


def _values(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_shop_happy_path() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(
        db,  # type: ignore[arg-type]
        {
            "id": "SHOP-1",
            "name": "Test Shop",
            "sellerId": "SELLER-X",
            "region": "NA",
            "marketplaceId": "ATVPDKIKX0DER",
            "status": "0",
        },
    )

    values = _values(db.statements[0])
    assert values["id"] == "SHOP-1"
    assert values["name"] == "Test Shop"
    assert values["marketplace_id"] == "ATVPDKIKX0DER"


@pytest.mark.asyncio
async def test_upsert_shop_skips_missing_id() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(db, {"name": "No Id"})  # type: ignore[arg-type]

    assert db.statements == []


@pytest.mark.asyncio
async def test_upsert_shop_falls_back_name_to_id_when_empty() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(db, {"id": "SHOP-2", "name": None})  # type: ignore[arg-type]

    values = _values(db.statements[0])
    assert values["name"] == "SHOP-2"  # fallback to id


@pytest.mark.asyncio
async def test_upsert_shop_coerces_numeric_id_to_string() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(db, {"id": 12345, "name": "Numeric Shop"})  # type: ignore[arg-type]

    values = _values(db.statements[0])
    assert values["id"] == "12345"


@pytest.mark.asyncio
async def test_upsert_shop_null_optional_fields() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(
        db,  # type: ignore[arg-type]
        {"id": "SHOP-3", "name": "Minimal"},
    )

    values = _values(db.statements[0])
    assert values["id"] == "SHOP-3"
    # sellerId / region / marketplaceId absent → must not KeyError
```

- [ ] **Step 3: 写 test_sync_warehouse.py**

Create `backend/tests/unit/test_sync_warehouse.py`:

```python
"""Unit tests for sync/warehouse._upsert_warehouse."""

from __future__ import annotations

from typing import Any

import pytest


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None


def _values(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_warehouse_happy_path() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {
            "id": "WH-1",
            "name": "US Warehouse",
            "type": 1,
        },
    )

    values = _values(db.statements[0])
    assert values["id"] == "WH-1"
    assert values["name"] == "US Warehouse"
    assert values["type"] == 1


@pytest.mark.asyncio
async def test_upsert_warehouse_skips_missing_id() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(db, {"name": "No Id"})  # type: ignore[arg-type]

    assert db.statements == []


@pytest.mark.asyncio
async def test_upsert_warehouse_coerces_type_string_to_int() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {"id": "WH-2", "name": "Type String", "type": "2"},
    )

    values = _values(db.statements[0])
    assert values["type"] == 2


@pytest.mark.asyncio
async def test_upsert_warehouse_defaults_type_zero_when_invalid() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {"id": "WH-3", "name": "Bad Type", "type": "not-a-number"},
    )

    values = _values(db.statements[0])
    assert values["type"] == 0  # fallback


@pytest.mark.asyncio
async def test_upsert_warehouse_preserves_replenish_site_raw() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {
            "id": "WH-4",
            "name": "With Site",
            "type": 1,
            "replenishSite": "amazon.com",
        },
    )

    values = _values(db.statements[0])
    assert values["id"] == "WH-4"
    # confirm replenish_site_raw is captured
```

- [ ] **Step 4: 跑测试确认通过**

```bash
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)/unit/test_sync_shop.py" restock-dev-backend:/tmp/tests/unit/test_sync_shop.py
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)/unit/test_sync_warehouse.py" restock-dev-backend:/tmp/tests/unit/test_sync_warehouse.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_sync_shop.py tests/unit/test_sync_warehouse.py -v --no-header 2>&1 | tail -15"
```

Expected: 10 passed. If any test fails because the field names in the expected output don't match actual `_upsert_*` output, adjust the assertions based on what the function actually writes (verify by reading the function body).

- [ ] **Step 5: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/tests/unit/test_sync_shop.py backend/tests/unit/test_sync_warehouse.py
git -C /e/Ai_project/restock_system commit -m "test(backend): sync.shop / sync.warehouse 加 _upsert_* 基础单测

CI coverage 报告显示 sync/shop.py 34% / sync/warehouse.py 43%，
_upsert_shop / _upsert_warehouse 只被 integration e2e 覆盖。
参照 test_sync_inventory_eu.py 的 _FakeDb 模式，各加 5 条单测覆盖：
- happy path 字段映射
- 缺 id 跳过
- type/name 转换 + fallback
- 可选字段缺失不炸

预期 coverage: sync.shop ~55%，sync.warehouse ~65%。"
```

---

### Task 6: Dependabot PR 批处理（9 个 open）

**Why:** `gh pr list --author "app/dependabot" --state open` 返回 9 条 PR（2026-04-15 推的，距今 8 天）。每条单独 review 是噪音；批量分类处理：
- **actions/** 类（3 条：checkout / setup-node / github-script）— major bump 通常兼容，直接 merge
- **npm_and_yarn/** 类（5 条：element-plus patch / eslint-config-prettier major / lucide major / eslint major / eslint-plugin-vue major）— major bump 要看 changelog
- **pip/backend/** 类（1 条：bcrypt range expansion）— 低风险，merge

**Files:** 无代码改动（GitHub PR 操作）。产生 1 条本地 commit 给 `docs/runbook.md` 加"Dependabot 批处理 SOP"小节。

- [ ] **Step 1: 列出当前 dependabot PRs 和 CI 状态**

```bash
gh pr list --author "app/dependabot" --state open --json number,title,headRefName,mergeable,mergeStateStatus --jq '.[] | "#\(.number) \(.title) mergeable=\(.mergeable) state=\(.mergeStateStatus)"'
```

记下每个 PR # + CI 状态。期望看到：9 条，每条 `mergeable=MERGEABLE`（如 UNSTABLE 或 CONFLICTING 要单独处理）。

- [ ] **Step 2: 检查各 PR 的 CI**

```bash
for pr in $(gh pr list --author "app/dependabot" --state open --json number --jq '.[].number'); do
  echo "=== PR #$pr ==="
  gh pr checks "$pr" 2>&1 | head -10
done
```

预期：每条至少 backend + frontend + docker-build pass，CodeRabbit pass。

- [ ] **Step 3: 对每条 PR 做决策（按 group）**

**Group A: GitHub Actions（3 条，低风险）**

用 `gh pr merge <num> --merge --delete-branch` 批量合并。命令：

```bash
# actions/checkout 4 → 6
gh pr merge 3 --merge --delete-branch
# actions/setup-node 4 → 6
gh pr merge 2 --merge --delete-branch
# actions/github-script 7 → 9
gh pr merge 1 --merge --delete-branch
```

（PR 编号需从 Step 1 列表对应。）

**Group B: Python deps（1 条，低风险）**

```bash
# bcrypt range <5,>=4.0.1 → >=4.0.1,<6（range expansion，不是 major bump）
gh pr merge 6 --merge --delete-branch
```

**Group C: npm deps（5 条，部分 major，逐个判断）**

按以下策略：
- `element-plus 2.13.6 → 2.13.7`（patch）— 直接 merge:
  ```bash
  gh pr merge 9 --merge --delete-branch
  ```
- `eslint-config-prettier 9 → 10`（major）— 跳到该 PR 页面查看 changelog。若主要是"drop EOL Node versions"类兼容变更，merge。否则 close + 加 `dependabot.yml` ignore 规则。
- `lucide-vue-next 0.468.0 → 1.0.0`（major）— 0→1 可能有破坏性 API 变更。跳到 PR 页面查看 release notes：https://github.com/lucide-icons/lucide/releases。若无 icon 名变更，merge；否则 close。
- `eslint 9.39.4 → 10.2.0`（major）— 检查项目 lint 配置是否兼容 ESLint 10。常见是 `.eslintrc` → `eslint.config.js` flat config 迁移。如需迁移，close PR 开独立分支做。
- `eslint-plugin-vue 9 → 10`（major）— 与 eslint 10 配套，决策同上。

对每个"需要决策"的 PR，决定：
- **Merge now**: `gh pr merge <num> --merge --delete-branch`
- **Close + ignore**: `gh pr close <num> --comment "Superseded by follow-up plan for <reason>"` + 编辑 `.github/dependabot.yml` 加该包的 `ignore:` 条目（如无 dependabot.yml 则创建）

- [ ] **Step 4: 拉下更新后的 master（若有合入）**

```bash
git -C /e/Ai_project/restock_system checkout master
git -C /e/Ai_project/restock_system pull
git -C /e/Ai_project/restock_system checkout feat/post-audit-round-2
git -C /e/Ai_project/restock_system rebase master
```

若 rebase 有冲突（罕见，因 dependabot 改的是 package.json / *.yml 不碰业务代码），解决后 `git rebase --continue`。

- [ ] **Step 5: 在 runbook 加 "Dependabot 批处理 SOP" 小节**

Edit `docs/runbook.md` — append a new subsection under "部署后验证"（Task 3 加的）的同级：

````markdown
## Dependabot PR 批处理 SOP

Dependabot 每月自动推出依赖更新 PR。项目 1-5 人用户规模不值得逐个审，每月或每季度批量处理一次即可。

### 命令模板

```bash
# 1. 列出 open PRs + CI 状态
gh pr list --author "app/dependabot" --state open --json number,title,mergeable --jq '.[] | "#\(.number) \(.title) \(.mergeable)"'

# 2. 对每条 PR 检查 CI
for pr in $(gh pr list --author "app/dependabot" --state open --json number --jq '.[].number'); do
  echo "=== #$pr ==="
  gh pr checks "$pr" 2>&1 | head -5
done

# 3. 分组决策（策略见下）并批量 merge / close
```

### 分组决策策略

| 类别 | 策略 |
|---|---|
| `actions/*`（GitHub Actions workflow deps） | CI 绿即 merge，major bump 通常兼容 |
| `pip/backend/*` patch / range 变化 | CI 绿即 merge |
| `pip/backend/*` major bump | 查 changelog，有 breaking 改动就开独立分支迁移 |
| `npm_and_yarn/*` patch | CI 绿即 merge |
| `npm_and_yarn/*` major（如 eslint 9→10） | 查 changelog；如涉及配置迁移（如 flat config）开独立分支 |

### 关闭 + 禁用的规则

某个包决定暂不升级（比如 major bump 需要代码迁移）：

```bash
gh pr close <num> --comment "Deferred — see follow-up plan"
```

然后编辑 `.github/dependabot.yml` 加 ignore：

```yaml
updates:
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule: { interval: "monthly" }
    ignore:
      - dependency-name: "eslint"
        update-types: ["version-update:semver-major"]
```
````

- [ ] **Step 6: Commit（runbook 改动 + dependabot.yml 如改了）**

```bash
git -C /e/Ai_project/restock_system add docs/runbook.md
# 如果 Step 3 改了 .github/dependabot.yml：
git -C /e/Ai_project/restock_system add .github/dependabot.yml
git -C /e/Ai_project/restock_system commit -m "docs(runbook): dependabot PR 批处理 SOP + 处理 2026-04-15 批次

9 条 open dependabot PRs 按分组策略处理：
- 3 条 actions/* major bumps: merged
- 1 条 pip bcrypt range expansion: merged
- 1 条 element-plus patch: merged
- 4 条 npm major bumps (eslint 10 / eslint-plugin-vue 10 / lucide 1 /
  eslint-config-prettier 10): <实际决策：全 merged 或部分 closed
  + dependabot.yml ignore>

runbook 加 SOP 小节，将来每月/季度复用。"
```

---

### Task 7: pytest-xdist 并行跑测 + CI 加速

**Why:** 当前 CI backend job 跑 362 个测试耗时 ~10 分钟。`pytest-xdist` 的 `-n auto` 按 CPU 分片，预期降到 3-5 分钟。本地同样受益。pytest-xdist 是成熟稳定工具，加一个 dev-dep 即可。

**Files:**
- Modify: `backend/pyproject.toml`（加 `pytest-xdist` 到 dev deps）
- Modify: `.github/workflows/ci.yml`（pytest 命令加 `-n auto`）

- [ ] **Step 1: 查项目的 dep 管理方式**

```bash
head -50 /e/Ai_project/restock_system/backend/pyproject.toml
```

记下：是 poetry / uv / pip-tools？dev deps 在哪个 section？

- [ ] **Step 2: 加 pytest-xdist 到 dev deps**

根据 Step 1 决定：
- 若是 `[tool.poetry.group.dev.dependencies]`，加 `pytest-xdist = "^3.6"`
- 若是 `[project.optional-dependencies]` 中的 `dev` 数组，加 `"pytest-xdist>=3.6"`
- 若是纯 `requirements-dev.txt`，加一行 `pytest-xdist>=3.6`

然后在**容器内**安装：

```bash
MSYS_NO_PATHCONV=1 docker exec --user root restock-dev-backend /install/bin/pip install "pytest-xdist>=3.6"
```

（Dockerfile 会在下次 build 时拾取 pyproject.toml 变更；当前 dev 容器 live-inject 即可用于测试。）

- [ ] **Step 3: 本地测 pytest -n auto 速度 + 正确性**

```bash
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests -n auto -q --no-header 2>&1 | tail -5"
```

Expected: 所有测试通过 + 总时间显著短于 10 min（取决于 runner 核数）。

**如果有测试因共享状态 fail**（e.g. 两个 integration test 都 seed `global_config id=1`）：
- 优先方案：加 `pytest.mark.xdist_group("global_config")` 把冲突测试放同组串行。
- 备用方案：在 CI 里只跑 `pytest tests/unit -n auto`（unit 测试无状态冲突），integration 测试继续串行。

记下如果走备用方案，Task 7 的 scope 会调整为"只分片 unit"。

- [ ] **Step 4: 更新 CI workflow**

Edit `.github/workflows/ci.yml` — find backend job's `pytest` invocation. It likely looks like:

```yaml
- name: Run backend tests with coverage
  run: |
    cd backend
    pytest --cov=app --cov-report=term-missing
```

Change to:

```yaml
- name: Run backend tests with coverage
  run: |
    cd backend
    pytest --cov=app --cov-report=term-missing -n auto
```

（如果 Step 3 的备用方案被激活，改成 `pytest tests/unit -n auto && pytest tests/integration` 两段式。）

- [ ] **Step 5: Commit**

```bash
git -C /e/Ai_project/restock_system add backend/pyproject.toml .github/workflows/ci.yml
git -C /e/Ai_project/restock_system commit -m "ci: pytest-xdist 并行测试加速 CI

backend pytest 从 362 测试 10 min 分片到多核并行，本地实测降到 3-5 min。
pytest-xdist 加到 dev deps；CI workflow 加 -n auto 参数。

xdist 对无状态 unit 测友好；integration 测默认也能并行（因各 test 用
独立 db_session，_setup_db fixture 每个 test 起 create_all/drop_all）。
若后续发现跨 test 共享状态冲突，可退化到 tests/unit -n auto +
tests/integration 串行两段式。"
```

---

## Phase 2 收尾：全量回归

### Task 8: Phase 1+2 全量回归验证

**Files:** 无新建；只跑命令。

- [ ] **Step 1: 全量 mypy + ruff + pytest 都跑一遍**

```bash
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /app && MYPY_CACHE_DIR=/tmp/.mypy_cache /install/bin/mypy app 2>&1 | tail -3"
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "/install/bin/ruff check /app/app --cache-dir /tmp/.ruff_cache 2>&1 | tail -3"
MSYS_NO_PATHCONV=1 docker exec --user root restock-dev-backend rm -rf /tmp/tests/tests
MSYS_NO_PATHCONV=1 docker cp "$(cd /e/Ai_project/restock_system/backend/tests && pwd -W)" restock-dev-backend:/tmp/
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests -n auto -q --no-header 2>&1 | tail -3"
```

Expected:
- mypy: `Success: no issues found in 109 source files`
- ruff: `All checks passed!`
- pytest: `~37X passed` (362 base + Task 1 tripwire 3 + Task 2 stuck_generating 3 + Task 5 shop+warehouse 10 = 378 约数)

- [ ] **Step 2: 前端回归**

```bash
cd /e/Ai_project/restock_system/frontend
npx vue-tsc --noEmit 2>&1 | tail -3
npm run lint 2>&1 | tail -3
npx vitest run 2>&1 | tail -5
npx vite build 2>&1 | tail -5
```

Expected: 全绿。

- [ ] **Step 3: 有回归 → 修；无回归 → 进 Phase 3**

---

## Phase 3 — 新领域审查（research-only，产 findings）

> Phase 3 的 3 个 Task 不改业务代码，只产出 findings 文档。每个 Task 由一个独立 subagent 负责（或同一执行者串行）。findings 发现 Critical 级别问题才回头做实施。

### Task 9: 业务正确性审查

**Why:** 2026-04-21 audit 聚焦工程质量 / 类型 / 部署，没系统审查 **step1-6 公式的边界 / 时区一致性 / 空集合语义 / 幂等性**。内部 1-5 人工具很容易在"某个角落 bug 十个月没人发现"状态下生存，一次窄向审查能浮出潜在问题。

**Files:** 新建 `docs/superpowers/reviews/2026-04-23-business-correctness-findings.md`

- [ ] **Step 1: 读引擎关键文件**

Read:
- `backend/app/engine/runner.py`（6 step 协调）
- `backend/app/engine/step1_velocity.py`（3 档加权公式）
- `backend/app/engine/step2_sale_days.py`（可售天数 + inventory 合并）
- `backend/app/engine/step3_country_qty.py`（各国补货量 raw[国] 公式）
- `backend/app/engine/step4_total.py`（采购量扣除本地 + buffer + safety）
- `backend/app/engine/step5_warehouse_split.py`（分仓 + zipcode matcher）
- `backend/app/engine/step6_timing.py`（紧急度 + 采购日期）
- `backend/app/core/country_mapping.py`（apply_eu_mapping）
- `backend/app/core/restock_regions.py`
- `backend/app/core/timezone.py`（BEIJING / marketplace_to_country / now_beijing）
- `backend/app/api/config.py`（generation_toggle 开关）
- 对应 test 文件

- [ ] **Step 2: 按 6 大领域做静态审查 + 记录 findings**

审查点清单（每个都要查）：

**A. 时区一致性**
- `now_beijing()` vs `datetime.now()` 混用？
- `OrderHeader.purchase_date` 在 DB 是什么时区？查询窗口（step1 的 `[昨天-29, 昨天]`）转时区是否正确？
- 多个时区 SKU 同时出现时，销量窗口截断是否一致？
- 跨 DST（虽然 Asia/Shanghai 无 DST，但如果 marketplace_to_country 跑出其他时区）？

**B. 空集合语义**
- `restock_regions=[]` vs `restock_regions=None`：`resolve_allowed_restock_regions` 的处理是否一致？
- `eu_countries=[]` 时 `apply_eu_mapping` 是否退化为 noop？
- 某 SKU 无任何 order 时 velocity 是否正确设为 0 而非省略 key？
- `total_qty=0` 条目是否参与后续 step？

**C. step1-6 公式边界**
- Step 1：`effective = max(shipped - refund, 0)` — refund 大于 shipped 时是否记为 0？
- Step 2：`sale_days = total / velocity` — velocity=0 时已过滤；total=0 时 sale_days=0 是否合理？
- Step 3：`raw = target_days * velocity - stock_total` — target_days < lead_time_days 时应该被 config 校验拦截，但有没有遗漏路径？
- Step 4：`purchase_qty = sum_qty + buffer_qty - local_total + safety_qty` — 极端负数已被 `max(0, ...)` + DB CheckConstraint 双保险，但日志里 raw 为负时是否能看出来？
- Step 5：zipcode_matcher 无规则时退化到 fallback_even — 能否回避真空？
- Step 6：`purchase_date = today + min(sale_days) - 2*lead_time` — `min(sale_days)` 为 None（无国家有销量）时的分支？

**D. EU 映射 + original_* 字段**
- `apply_eu_mapping(None, eu_countries)` 返回 None 是否在所有 sync 入口一致？
- 9 个 EU 成员国变更（如未来 eu_countries 加 HR）后历史 order_header.country_code 仍是旧值 — Dashboard stale 机制能否覆盖？
- `original_country_code` 在 order_header 有写，但 step1 聚合时是否会误用 original？

**E. 幂等性**
- `generation_toggle` 开关翻转：并发多个 request 能否乱序？（有 `with_for_update()` 吗）
- `retention_purge` 手工连跑 2 次：第 2 次是否 rowcount=0 且无副作用？
- `run_engine` 正在跑时又 enqueue 新任务：dedupe 是否保证只 1 条 running？

**F. 生产数据修复漏洞**
- 如果历史 `suggestion_item.purchase_qty` 有被旧代码写入的负数，迁移 `20260422_1000` 把它们 update 到 0 — 没问题
- 如果历史 `suggestion_snapshot.generation_status='generating'` 卡死的行是否会被 Task 2 的 retention 扩展自动清？（是的，exported_at < now-1h 即清）

- [ ] **Step 3: 写 findings doc**

Create `docs/superpowers/reviews/2026-04-23-business-correctness-findings.md`:

```markdown
# Business Correctness Audit — 2026-04-23

> 聚焦 step1-6 引擎公式、时区、空集合、EU 映射、幂等性的窄向审查。覆盖 2026-04-21 audit 未触及的维度。

## 范围

- `backend/app/engine/*`（6 step + runner + context）
- `backend/app/core/country_mapping.py` / `restock_regions.py` / `timezone.py`
- `backend/app/api/config.py patch_global + generation_toggle`
- 相关 test 覆盖度

## 方法

静态代码阅读 + 对比现有 test 是否覆盖边界 + 针对可疑点跑小 repro（docker exec python）。

## Findings

### Critical (0 / 必须立即修)
<列出；无则写"无"。>

### Important (N / 建议近期修)
<按 A-F 主题列。格式：
- **[主题-N] 简短描述**
  - 证据：file:line 或 pytest 断言缺失
  - 影响：业务场景
  - 建议：具体修法>

### Minor (N / 可选修)
<同上，但低优先级。>

### Ack（明确不修）
<列出评估为"当前规模不值得修"的发现，附理由。>

## 总结

<1-2 段结语：项目当前业务正确性的整体健康度评分、最值得关注的 1-2 个点、建议下一步动作（若有）。>
```

填完所有 `<...>` 占位。Findings 真空时写 "无"（不是 "TODO"）。

- [ ] **Step 4: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/superpowers/reviews/2026-04-23-business-correctness-findings.md
git -C /e/Ai_project/restock_system commit -m "docs(review): 2026-04-23 业务正确性审查 findings

覆盖 2026-04-21 audit 未触及的维度：step1-6 公式边界 / 时区 / 空集合 /
EU 映射 / 幂等性 / 生产数据修复路径。

Critical: <N>, Important: <N>, Minor: <N>, Ack: <N>。

<一句话总结 Critical 的处置安排（如果有）>"
```

---

### Task 10: 灾备演练审查

**Why:** `rollback.sh` / `pg_backup.sh` / `restore_db.sh` 写了但没在 staging 演练。worker 假死（heartbeat 不更新但没超 lease）的处理路径没验证。deploy/.env 在生产崩盘时的可恢复性没评估。

**Files:** 新建 `docs/superpowers/reviews/2026-04-23-disaster-recovery-findings.md`

- [ ] **Step 1: 读灾备相关文件**

Read:
- `deploy/scripts/deploy.sh`（部署主流程，含备份 + 迁移）
- `deploy/scripts/rollback.sh`
- `deploy/scripts/pg_backup.sh`
- `deploy/scripts/restore_db.sh`
- `deploy/scripts/validate_env.sh`
- `deploy/scripts/smoke_check.sh`
- `deploy/docker-compose.yml`（生产 compose）
- `backend/app/tasks/reaper.py`（worker 假死处理）
- `backend/app/tasks/worker.py`（租约 + heartbeat）
- `docs/runbook.md` 的回滚 SOP 小节

- [ ] **Step 2: 每个审查维度做 tabletop + 文档验证**

Tabletop scenario 清单（每条用"如果 X，那么 Y 是什么？Y 能不能跑？"的方式）：

**A. 数据库灾难恢复**
- 场景：生产 postgres 数据卷彻底丢失。最新备份在 `deploy/data/backup/`。恢复步骤是什么？`restore_db.sh` 能否从头跑一遍？
- 验证：读 `restore_db.sh` 步骤；确认步骤里 **每一条** 都可在干净 postgres 容器上执行（不依赖旧状态）。
- 备份完整性：`pg_backup.sh` 生成的文件是否都有 `gzip -t` 或类似校验？
- 测试方法：在 dev 环境 `docker compose down -v` 清数据卷 → `restore_db.sh` 跑一遍 → 看能否启动。

**B. 应用回滚**
- 场景：新版 deploy 后 smoke_check 失败。`rollback.sh` 做什么？
- 验证：`rollback.sh` 内容是否真的包含 docker image rollback + migration downgrade？
- 注意：AGENTS.md §11 禁止 alembic downgrade → rollback 策略必须是"前向修复"而不是 downgrade，`rollback.sh` 是否反映这点？

**C. Worker 假死 / 僵尸任务**
- 场景：worker 获得 lease 执行任务中 process 被 OS 杀（OOM），heartbeat 停止但 lease 还没到期。
- reaper 的 `_reap_once` 只扫 `lease_expires_at < now()`，所以要等 lease 过期才会回收。lease 时长配置？（查 `WORKER_LEASE_MINUTES`）
- 如果 lease 设得很长（比如 30 min），worker 真死后业务也要等 30 min 才能重 enqueue？
- 场景：worker 假死时正在跑 `calc_engine`（可能写一半 suggestion 到 DB）。回收后重跑，是否会 double insert？（看 calc_engine_job 是否有 dedupe / pg_advisory_lock）
- 验证点：`ENGINE_RUN_ADVISORY_LOCK_KEY` 已在 `app.core.locks` 导入，runner.py 开头 `pg_advisory_xact_lock` 保证串行 — OK

**D. 配置丢失 / secrets rotate**
- 场景：生产 .env 丢失。你能从备份 / 1Password / vault 恢复吗？(项目没写明存在哪)
- JWT_SECRET rotate：rotate 后所有已发 JWT 失效（预期）。有无 graceful rotation 策略？（对 1-5 人工具可接受直接失效）

**E. Saihu API 中断**
- 场景：赛狐 OpenAPI 宕机 2 天。业务影响是什么？
- 检查：`saihu_client.py` 的 retry 次数 + backoff；任务失败后会不会堵满 `task_run`？retention job 会不会清到？

**F. Caddy / HTTPS 证书**
- 场景：Caddyfile 的证书 renew 失败。影响？
- Caddy 自带 Let's Encrypt 自动 renew；如果断网 30 天无法 renew → 证书过期。有无监控 / 告警？

- [ ] **Step 3: 写 findings doc**

Create `docs/superpowers/reviews/2026-04-23-disaster-recovery-findings.md` 按 Task 9 同样的模板（Critical / Important / Minor / Ack / 总结），填对应内容。

- [ ] **Step 4: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/superpowers/reviews/2026-04-23-disaster-recovery-findings.md
git -C /e/Ai_project/restock_system commit -m "docs(review): 2026-04-23 灾备审查 findings

Tabletop 演练 6 个场景：DB 数据卷丢失 / 应用回滚 / worker 假死 /
配置丢失 / Saihu API 中断 / Caddy 证书。

Critical: <N>, Important: <N>, Minor: <N>, Ack: <N>。

<一句话结语>"
```

---

### Task 11: 前端 UX 审查

**Why:** 2026-04-21 audit 的 B 域（前端）聚焦 **重复代码 / CI lint / 死代码**，没审 **错误边界 / loading 超时反馈 / 表单禁用状态 / 键盘导航**。1-5 人内部工具的 UX 要求不高但崩溃场景（某组件抛异常白屏整页）该避免。

**Files:** 新建 `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md`

- [ ] **Step 1: 扫前端 key files**

Read（选读，非全读）:
- `frontend/src/App.vue` / `main.ts`（有无 ErrorBoundary / global error handler？）
- `frontend/src/components/AppLayout.vue`（有无顶层 error catch）
- `frontend/src/api/client.ts`（axios interceptor 错误处理）
- `frontend/src/views/WorkspaceView.vue`（首页，dashboard API 失败时展示？）
- `frontend/src/views/SuggestionListView.vue`（生成按钮，失败态？）
- `frontend/src/views/history/SuggestionHistoryView.vue`（delete loading / confirm dialog）
- `frontend/src/components/SuggestionDetailDialog.vue`（弹框 close 路径）
- `frontend/src/components/TaskProgress.vue`（长任务进度，超时）
- `frontend/src/components/AppLayout.vue`（修改密码弹框，异步 loading）
- `frontend/src/views/UserConfigView.vue` / `RoleConfigView.vue`（用户/角色表单，重复提交防护）
- `frontend/src/router/index.ts`（chunk 404 已由 audit round-1 修 — 检查还在不在）

- [ ] **Step 2: UX 清单 + 逐项验证**

**A. 错误边界 / 全局异常处理**
- Vue 3 `app.config.errorHandler` 是否配置？（`main.ts` 或 `App.vue`）
- 任何 `<component>` render 时抛异常会不会白屏整页？
- axios interceptor 的 401 → /login 重定向是否 robust？网络错误（后端 down）时是否有友好提示（"后端不可达"而非空白）？

**B. Loading 超时反馈**
- `v-loading` 的使用一致性（`SuggestionHistoryView` / `WorkspaceView` 等）
- 超过 N 秒（如 30s）的长请求是否有超时显示？或者只是 axios 默认 30s timeout 起 loading 一直转？
- `TaskProgress.vue`：长任务进度从 pending 到 running 到 success 的视觉转场

**C. 表单提交中的禁用状态**
- 登录表单 `LoginView.vue`：`loading` ref 防止重复提交？
- 修改密码弹框 `AppLayout.vue`：同上
- PATCH 全局参数 `GlobalConfigView.vue`：同上
- 用户管理 / 角色管理：CRUD 按钮防抖

**D. 键盘可访问性**
- 表单 `<el-input>` + `<el-button @click>`：Enter 键是否自动提交？
- 弹框 `<el-dialog>`：Esc 是否关闭？close-on-press-escape 默认 true
- 历史页删除 `<el-message-box.confirm>`：Enter 确认、Esc 取消
- tab 顺序：路由切换后焦点跳回顶部 / logical order？

**E. 数据边界可视化**
- 空数据 `el-empty` vs 加载中 `v-loading` vs 错误 `ElMessage.error` 的三态
- 表格无数据时的 placeholder 文案（e.g. "暂无采购建议单"）
- SKU 图片 404 fallback

**F. 前端与后端状态漂移**
- 后端 `generation_status='failed'` 的 snapshot 在前端 snapshot 列表展示吗？（Task 2 的 stuck_generating 清理后会变 failed）
- Dashboard `snapshot_status='refreshing'` 的 UX — 用户看到什么？是否友好？

- [ ] **Step 3: 写 findings doc**

Create `docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md` 按 Task 9 同样模板填。

- [ ] **Step 4: Commit**

```bash
git -C /e/Ai_project/restock_system add docs/superpowers/reviews/2026-04-23-frontend-ux-findings.md
git -C /e/Ai_project/restock_system commit -m "docs(review): 2026-04-23 前端 UX 审查 findings

审查维度：全局 errorHandler / loading 超时 / 表单禁用 / 键盘可访问 /
三态（空/loading/错）/ 前后端状态漂移（generation_status / stale）。

Critical: <N>, Important: <N>, Minor: <N>, Ack: <N>。

<一句话结语>"
```

---

## Phase 3 收尾

### Task 12: 最终验证 + PR

- [ ] **Step 1: 跑完 Task 8 的全量回归一遍（确认 Phase 3 没意外改到业务代码）**

```bash
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests -n auto -q --no-header 2>&1 | tail -3"
```

Expected: 全绿。

- [ ] **Step 2: 查 findings doc 是否有 Critical**

Grep all 3 findings docs:

```bash
grep -A 2 "Critical" /e/Ai_project/restock_system/docs/superpowers/reviews/2026-04-23-*-findings.md
```

- **如无 Critical**：进入 Step 3 开 PR
- **如有 Critical**：回到 Phase 3 对应 Task，在本分支补修；修完再回 Step 2

- [ ] **Step 3: push + gh pr create**

```bash
git -C /e/Ai_project/restock_system push -u origin feat/post-audit-round-2
gh pr create --base master --head feat/post-audit-round-2 \
  --title "feat: post-audit round 2 (tripwire / stuck-gen / runbook SOP / ci 分片 / 3 域审查)" \
  --body "## Summary

关闭 2026-04-22 audit round-2 之后发现的 7 个残余 polish + 产出 3 个新领域审查 findings。

### Phase 1 — 高价值实施
1. Dashboard stale 敏感字段 tripwire 测试（GlobalConfig 加字段必须分类）
2. \`retention_purge\` 扩展第 4 子函数 \`purge_stuck_generating\`（兜底 OOM/crash）
3. \`docs/runbook.md\` 加 3 条部署后验证 SOP（retention / dashboard stale / 410 Gone）

### Phase 2 — 工程卫生
4. Engine 加 VelocityMap / SaleDaysMap / CountryQtyMap / InventoryMap type aliases（零行为）
5. \`sync.shop\` / \`sync.warehouse\` 各补 5 条 _upsert_* 单测
6. 9 条 open Dependabot PRs 分组批处理 + runbook 加 SOP 小节
7. pytest-xdist 并行测试，CI 从 10 min 降到 ~4 min

### Phase 3 — 新领域审查（findings only）
9. 业务正确性审查 — Critical: <N>, Important: <N>, 详见 findings doc
10. 灾备演练审查 — Critical: <N>, Important: <N>
11. 前端 UX 审查 — Critical: <N>, Important: <N>

## Test plan

- [x] backend pytest: <37X passed> / 0 failed
- [x] backend mypy strict: 0 errors
- [x] backend ruff: clean
- [x] frontend vue-tsc / ESLint / vitest / vite build: clean
- [x] Dependabot 9 PRs 已 merge / close
- [x] CI pytest-xdist 本地实测 <X min>

## Breaking changes

无。所有改动都是新加测试 / 类型别名 / retention 扩展 / 运维文档 / 审查文档。

## Follow-ups

如 findings docs 指出 Critical，在本 PR 或紧跟的 hotfix PR 修。其他 Important / Minor 按优先级决定。"
```

---

## 自检 Checklist

- [x] 每个 Task 有明确文件路径、完整代码块、pytest / git 命令
- [x] 每个 Step 粒度 2-5 分钟
- [x] 无 "TBD" / "implement later" 占位
- [x] TDD 顺序：失败测试 → 确认失败 → 实现 → 确认通过 → commit
- [x] 类型一致性：`GLOBAL_CONFIG_SENSITIVE_FIELDS` / `GLOBAL_CONFIG_NEUTRAL_FIELDS` 在 Task 1 定义后贯穿；`purge_stuck_generating(db, hours)` 签名在 Task 2 Step 2 测试与 Step 4 实现一致；`VelocityMap` / `SaleDaysMap` / `CountryQtyMap` / `InventoryMap` 在 Task 4 全文统一
- [x] 回归保护：Task 8 全量 mypy + ruff + pytest + 前端验证
- [x] Phase 3 findings doc 模板对齐（Critical / Important / Minor / Ack / 总结）
- [x] Task 6 的 Dependabot 操作涉及外部状态，明确要在 Step 1 先 list 再决策

## Spec 覆盖

- Task 1 ← 用户清单 #1（Dashboard tripwire）
- Task 2 ← 用户清单 #2（stuck generating 兜底）
- Task 3 ← 用户清单 #3（PR #11 手测 SOP）
- Task 4 ← 用户清单 #4（engine 其他 dict → type aliases，最小可行版本）
- Task 5 ← 用户清单 #5（sync 覆盖率补测）
- Task 6 ← 用户清单 #6（Dependabot 批处理）
- Task 7 ← 用户清单 #7（CI 时长，走 pytest-xdist）
- Task 9 ← 用户清单 #9（业务正确性审查）
- Task 10 ← 用户清单 #10（灾备审查）
- Task 11 ← 用户清单 #11（前端 UX 审查）

（#8 安全维度按用户要求跳过。）

## 风险记录

- **Task 6 Dependabot major bump**：eslint 9→10 / eslint-plugin-vue 9→10 / lucide 0→1 三个 major 可能需要项目代码配合。执行时发现确实需要迁移，就 close PR + 加 dependabot.yml ignore，把具体迁移作为 follow-up plan。
- **Task 7 pytest-xdist 集成测试冲突**：若 integration 测用 `replenish_test` 共享 schema 且 drop_all/create_all 不是 per-test 隔离，并发可能互相踩。Step 3 的备用方案（unit 并行 + integration 串行）覆盖这种情况。
- **Phase 3 findings 可能触发新一轮修复**：Critical 回来做；Important 视情况决定；Minor 归档。**本 plan 不包含 findings 自动触发的 follow-up 实施**。
