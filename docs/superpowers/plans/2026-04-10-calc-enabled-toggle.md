# Calc Enabled Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `calc_enabled` toggle so users can disable automatic replenishment calculation while keeping manual triggering available.

**Architecture:** Add `calc_enabled` boolean to GlobalConfig (backend model + migration + schema + scheduler logic), then add a switch to the frontend GlobalConfigView that hides the cron selector when disabled.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), Vue 3/TypeScript/Element Plus (frontend)

---

## File Map

| File | Action | Change |
|------|--------|--------|
| `backend/app/models/global_config.py` | Modify | Add `calc_enabled` column |
| `backend/app/schemas/config.py` | Modify | Add `calc_enabled` to Out and Patch schemas |
| `backend/app/tasks/scheduler.py` | Modify | Skip calc_engine job when `calc_enabled=False` |
| `backend/alembic/versions/20260410_0002_add_calc_enabled.py` | Create | Migration to add column |
| `backend/app/main.py` | Modify | Seed `calc_enabled=True` in `_ensure_global_config` |
| `frontend/src/api/config.ts` | Modify | Add `calc_enabled` to `GlobalConfig` interface |
| `frontend/src/views/GlobalConfigView.vue` | Modify | Add switch, hide cron when disabled |

---

### Task 1: Backend — Add `calc_enabled` to model and schema

**Files:**
- Modify: `backend/app/models/global_config.py`
- Modify: `backend/app/schemas/config.py`

- [ ] **Step 1: Add `calc_enabled` column to GlobalConfig model**

In `backend/app/models/global_config.py`, after line 33 (`scheduler_enabled`), add:

```python
    calc_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
```

- [ ] **Step 2: Add `calc_enabled` to schemas**

In `backend/app/schemas/config.py`:

Add to `GlobalConfigOut` (after `scheduler_enabled: bool`):
```python
    calc_enabled: bool
```

Add to `GlobalConfigPatch` (after `scheduler_enabled: bool | None = None`):
```python
    calc_enabled: bool | None = None
```

- [ ] **Step 3: Verify — run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All tests pass (schema changes are additive)

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/global_config.py backend/app/schemas/config.py
git commit -m "feat(backend): add calc_enabled field to GlobalConfig model and schema"
```

---

### Task 2: Backend — Create Alembic migration

**Files:**
- Create: `backend/alembic/versions/20260410_0002_add_calc_enabled.py`

- [ ] **Step 1: Create migration file**

Create `backend/alembic/versions/20260410_0002_add_calc_enabled.py`:

```python
"""Add calc_enabled to global_config.

Revision ID: 20260410_0002
Revises: 20260410_0001
Create Date: 2026-04-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260410_0002"
down_revision: str | Sequence[str] | None = "20260410_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column(
            "calc_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("global_config", "calc_enabled")
```

- [ ] **Step 2: Verify — check migration chain**

Run: `cd backend && python -m alembic heads`
Expected: Shows `20260410_0002` as the head

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/20260410_0002_add_calc_enabled.py
git commit -m "feat(backend): add migration for calc_enabled column"
```

---

### Task 3: Backend — Update scheduler to skip calc when disabled

**Files:**
- Modify: `backend/app/tasks/scheduler.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add `calc_enabled` to SchedulerRuntimeConfig**

In `backend/app/tasks/scheduler.py`, update the `SchedulerRuntimeConfig` dataclass (line 25-28):

```python
@dataclass(frozen=True)
class SchedulerRuntimeConfig:
    enabled: bool
    sync_interval_minutes: int
    calc_cron: str
    calc_enabled: bool
```

- [ ] **Step 2: Update `_load_scheduler_config` to read `calc_enabled`**

Find the `_load_scheduler_config` function and add `calc_enabled` to the select and return. Read the current function first to find exact lines, then add `GlobalConfig.calc_enabled` to the select columns and `calc_enabled=bool(row.calc_enabled)` to the return.

- [ ] **Step 3: Update `_register_jobs` to conditionally register calc_engine**

Change the `_register_jobs` function signature to accept `calc_enabled: bool`, and wrap the calc_engine job registration:

```python
def _register_jobs(
    scheduler: AsyncIOScheduler,
    *,
    sync_interval_minutes: int,
    calc_cron: str,
    calc_enabled: bool,
) -> None:
```

Wrap the calc_engine `scheduler.add_job` call (lines 114-120):

```python
    if calc_enabled:
        scheduler.add_job(
            _enqueue_safely,
            trigger=CronTrigger.from_crontab(calc_cron, timezone=BEIJING),
            args=["calc_engine"],
            id="trigger_calc_engine",
            replace_existing=True,
        )
    else:
        # Remove existing calc job if present
        try:
            scheduler.remove_job("trigger_calc_engine")
        except Exception:
            pass
```

- [ ] **Step 4: Update all callers of `_register_jobs` to pass `calc_enabled`**

Find all calls to `_register_jobs` (in `setup_scheduler`) and add `calc_enabled=config.calc_enabled`.

Also update the scheduler signature tuple to include `calc_enabled`:

```python
    signature = (config.sync_interval_minutes, config.calc_cron, config.calc_enabled)
```

- [ ] **Step 5: Update `_ensure_global_config` in `main.py`**

In `backend/app/main.py`, find the `_ensure_global_config` function's `pg_insert` values and add `calc_enabled=True`.

- [ ] **Step 6: Verify — run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/scheduler.py backend/app/main.py
git commit -m "feat(backend): skip calc_engine scheduler job when calc_enabled is false"
```

---

### Task 4: Frontend — Add `calc_enabled` toggle to GlobalConfigView

**Files:**
- Modify: `frontend/src/api/config.ts`
- Modify: `frontend/src/views/GlobalConfigView.vue`

- [ ] **Step 1: Add `calc_enabled` to frontend API interface**

In `frontend/src/api/config.ts`, add to the `GlobalConfig` interface (after `calc_cron: string`):

```typescript
  calc_enabled: boolean
```

- [ ] **Step 2: Add switch to GlobalConfigView template**

In `frontend/src/views/GlobalConfigView.vue`, in the "补货计算" card, add a switch BEFORE the cron form-item, and wrap the cron form-item in a `v-if`:

Replace the 补货计算 card's form content (lines 49-69) with:

```vue
      <el-form :model="form" label-width="180px" style="max-width: 560px">
        <el-form-item label="自动计算">
          <el-switch v-model="form.calc_enabled" />
        </el-form-item>
        <el-form-item v-if="form.calc_enabled" label="自动计算时间">
          <div class="cron-inline">
            <el-select v-model="selectedCronPreset" class="cron-select" @change="onCronPresetChange">
              <el-option
                v-for="preset in cronPresets"
                :key="preset.value"
                :label="preset.label"
                :value="preset.value"
              />
            </el-select>
            <el-input
              v-if="selectedCronPreset === '__custom__'"
              v-model="customCron"
              class="cron-input"
              placeholder="如: 30 6 1,15 (分 时 日 月 周)"
              @input="onCustomCronInput"
            />
          </div>
        </el-form-item>
      </el-form>
```

- [ ] **Step 3: Verify — run type check**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Verify — run vite build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/config.ts frontend/src/views/GlobalConfigView.vue
git commit -m "feat(ui): add calc_enabled toggle to global config page"
```

---

## Summary

| Task | Scope | What Changes |
|------|-------|-------------|
| 1 | Backend model + schema | Add `calc_enabled` boolean field |
| 2 | Backend migration | Alembic migration with `server_default=true` |
| 3 | Backend scheduler | Skip calc_engine registration when disabled |
| 4 | Frontend UI | Switch toggle + conditional cron display |
