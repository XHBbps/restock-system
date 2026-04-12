# Project Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all P0 (security/data integrity) and P1 (correctness/logic bugs) issues identified in the full project audit, plus high-value P2/P3 items.

**Architecture:** Fixes are organized into 4 phases: (1) security-critical backend fixes, (2) data integrity fixes, (3) frontend bug fixes, (4) infrastructure improvements. Each task is independent and can be committed separately.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / Vue 3 / TypeScript / Element Plus

---

## Phase 1: Security-Critical Backend Fixes

### Task 1: Replace `python-jose` with `PyJWT`

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/security.py`
- Test: `backend/tests/unit/test_security.py` (existing)

- [ ] **Step 1: Update `pyproject.toml` dependencies**

Replace `python-jose` with `PyJWT` and unpin `bcrypt`:

```toml
# In [project] dependencies, replace:
#   "python-jose[cryptography]>=3.3.0",
#   "bcrypt==4.0.1",
# With:
    "PyJWT>=2.9.0",
    "bcrypt>=4.0.1,<5",
```

- [ ] **Step 2: Rewrite `security.py` to use PyJWT**

Replace the full content of `backend/app/core/security.py`:

```python
"""密码哈希与 JWT 工具。"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import get_settings
from app.core.exceptions import Unauthorized


def hash_password(plain: str) -> str:
    """生成密码 bcrypt 哈希。"""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码哈希。"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str = "owner", extra: dict[str, Any] | None = None) -> str:
    """签发 JWT。

    单用户场景下 subject 固定为 'owner',可在 extra 中放入额外声明。
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.jwt_expires_hours)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """解码 + 校验 JWT,失败抛 Unauthorized。"""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise Unauthorized("token 无效或已过期") from exc
```

- [ ] **Step 3: Remove passlib deprecation filter from `pyproject.toml`**

In `pyproject.toml`, find the `filterwarnings` section and remove:

```toml
# Remove this line from [tool.pytest.ini_options] filterwarnings:
#   "ignore::DeprecationWarning:passlib.*",
```

Also remove `passlib[bcrypt]` from dependencies.

- [ ] **Step 4: Install updated dependencies**

Run: `cd backend && pip install -e ".[dev]"`
Expected: Installs PyJWT, removes python-jose and passlib

- [ ] **Step 5: Run existing security tests**

Run: `cd backend && python -m pytest tests/unit/test_security.py -v`
Expected: All tests PASS (the API is compatible)

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/core/security.py
git commit -m "$(cat <<'EOF'
fix(security): replace unmaintained python-jose/passlib with PyJWT/bcrypt

python-jose has known CVEs (CVE-2024-33663, CVE-2024-33664) and no
releases since 2022. passlib is also unmaintained since 2020. Switch to
PyJWT for JWT operations and use bcrypt directly for password hashing.
Also unpin bcrypt to allow security patch updates.
EOF
)"
```

---

### Task 2: Escape ILIKE wildcards in user input

**Files:**
- Modify: `backend/app/api/suggestion.py:62`
- Modify: `backend/app/api/config.py:117`
- Modify: `backend/app/api/data.py:103,107,238,306,430-431`
- Create: `backend/app/core/query.py`
- Create: `backend/tests/unit/test_query_utils.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_query_utils.py`:

```python
from app.core.query import escape_like


def test_escape_percent():
    assert escape_like("100%") == r"100\%"


def test_escape_underscore():
    assert escape_like("a_b") == r"a\_b"


def test_escape_backslash():
    assert escape_like(r"a\b") == r"a\\b"


def test_no_special_chars():
    assert escape_like("hello") == "hello"


def test_all_special_chars():
    assert escape_like(r"%_\") == r"\%\_\\"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_query_utils.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.query'"

- [ ] **Step 3: Write the escape_like utility**

Create `backend/app/core/query.py`:

```python
"""SQL query utilities."""


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards for safe use in patterns.

    Escapes %, _, and \\ so user input is treated as literal text.
    Use with .ilike(f"%{escape_like(value)}%", escape="\\\\").
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_query_utils.py -v`
Expected: All PASS

- [ ] **Step 5: Apply `escape_like` to `suggestion.py`**

In `backend/app/api/suggestion.py`, add import and fix the ILIKE call:

```python
# Add import at top:
from app.core.query import escape_like

# Line 62, change:
#   .where(SuggestionItem.commodity_sku.ilike(f"%{sku}%"))
# To:
            .where(SuggestionItem.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
```

- [ ] **Step 6: Apply `escape_like` to `config.py`**

In `backend/app/api/config.py`, add import and fix:

```python
# Add import at top:
from app.core.query import escape_like

# Line 117, change:
#   base = base.where(SkuConfig.commodity_sku.ilike(f"%{keyword}%"))
# To:
        base = base.where(SkuConfig.commodity_sku.ilike(f"%{escape_like(keyword)}%", escape="\\"))
```

- [ ] **Step 7: Apply `escape_like` to `data.py`**

In `backend/app/api/data.py`, add import and fix all ILIKE calls:

```python
# Add import at top:
from app.core.query import escape_like

# Line 103: change f"%{sku}%" to f"%{escape_like(sku)}%", escape="\\"
# Line 107: change f"%{sku}%" to f"%{escape_like(sku)}%", escape="\\"
# Line 238: change f"%{sku}%" to f"%{escape_like(sku)}%", escape="\\"
# Line 306: change f"%{sku}%" to f"%{escape_like(sku)}%", escape="\\"
# Lines 430-431: change f"%{sku}%" to f"%{escape_like(sku)}%", escape="\\"
```

Each `.ilike(f"%{sku}%")` becomes `.ilike(f"%{escape_like(sku)}%", escape="\\")`.

- [ ] **Step 8: Run full test suite**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/query.py backend/tests/unit/test_query_utils.py \
       backend/app/api/suggestion.py backend/app/api/config.py backend/app/api/data.py
git commit -m "$(cat <<'EOF'
fix(security): escape ILIKE wildcards in user search input

User-supplied % and _ characters in search parameters were passed
directly into ILIKE patterns, allowing unintended pattern matching.
Add escape_like() utility and apply to all search endpoints.
EOF
)"
```

---

### Task 3: Fix open redirect in LoginView

**Files:**
- Modify: `frontend/src/views/LoginView.vue:77`

- [ ] **Step 1: Fix the redirect validation**

In `frontend/src/views/LoginView.vue`, line 77, change:

```typescript
// Old:
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
// New:
    const raw = (route.query.redirect as string) || '/'
    const redirect = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
    router.replace(redirect)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "$(cat <<'EOF'
fix(security): validate login redirect to prevent open redirect

Ensure redirect parameter starts with / and not // to prevent
redirecting users to external domains after login.
EOF
)"
```

---

### Task 4: Fix deploy.sh to restart worker and scheduler

**Files:**
- Modify: `deploy/scripts/deploy.sh:33`

- [ ] **Step 1: Add worker and scheduler to the up command**

In `deploy/scripts/deploy.sh`, line 33, change:

```bash
# Old:
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend frontend caddy
# New:
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend worker scheduler frontend caddy
```

- [ ] **Step 2: Commit**

```bash
git add deploy/scripts/deploy.sh
git commit -m "$(cat <<'EOF'
fix(deploy): include worker and scheduler in deploy restart

Previously only backend/frontend/caddy were restarted, leaving
worker and scheduler running old code after deployments.
EOF
)"
```

---

## Phase 2: Data Integrity Fixes

### Task 5: Add Alembic migration for `scheduler_enabled` + daily archive unique constraint

**Files:**
- Create: `backend/alembic/versions/20260410_0001_add_scheduler_enabled_and_archive_uq.py`

- [ ] **Step 1: Create the migration**

Create `backend/alembic/versions/20260410_0001_add_scheduler_enabled_and_archive_uq.py`:

```python
"""Add scheduler_enabled column and daily archive unique constraint.

Revision ID: 20260410_0001
Revises: 20260409_1700
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from alembic import op

revision = "20260410_0001"
down_revision = "20260409_1700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add missing scheduler_enabled column to global_config
    op.add_column(
        "global_config",
        sa.Column(
            "scheduler_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # 2. Remove duplicate daily archive rows (keep first by id)
    op.execute(
        """
        DELETE FROM inventory_snapshot_history a
        USING inventory_snapshot_history b
        WHERE a.id > b.id
          AND a.commodity_sku = b.commodity_sku
          AND a.warehouse_id = b.warehouse_id
          AND a.snapshot_date = b.snapshot_date
        """
    )

    # 3. Add unique constraint to prevent future duplicates
    op.create_unique_constraint(
        "uq_snapshot_history_sku_wh_date",
        "inventory_snapshot_history",
        ["commodity_sku", "warehouse_id", "snapshot_date"],
    )

    # 4. Remove dead columns from global_config
    op.drop_column("global_config", "login_failed_count")
    op.drop_column("global_config", "login_locked_until")


def downgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column("login_locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "global_config",
        sa.Column(
            "login_failed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.drop_constraint(
        "uq_snapshot_history_sku_wh_date", "inventory_snapshot_history"
    )
    op.drop_column("global_config", "scheduler_enabled")
```

- [ ] **Step 2: Update GlobalConfig model to remove dead columns**

In `backend/app/models/global_config.py`, remove these lines:

```python
# Remove these two lines (around lines 45-48):
    login_failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Update daily_archive_job to use ON CONFLICT DO NOTHING**

In `backend/app/tasks/jobs/daily_archive.py`, line 25-31, change the SQL:

```python
# Old:
            text(
                """
                INSERT INTO inventory_snapshot_history
                  (commodity_sku, warehouse_id, country, available, reserved, snapshot_date)
                SELECT
                  commodity_sku, warehouse_id, country, available, reserved, :snapshot_date
                FROM inventory_snapshot_latest
                """
            ),
# New:
            text(
                """
                INSERT INTO inventory_snapshot_history
                  (commodity_sku, warehouse_id, country, available, reserved, snapshot_date)
                SELECT
                  commodity_sku, warehouse_id, country, available, reserved, :snapshot_date
                FROM inventory_snapshot_latest
                ON CONFLICT (commodity_sku, warehouse_id, snapshot_date) DO NOTHING
                """
            ),
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260410_0001_add_scheduler_enabled_and_archive_uq.py \
       backend/app/models/global_config.py \
       backend/app/tasks/jobs/daily_archive.py
git commit -m "$(cat <<'EOF'
fix(db): add scheduler_enabled column, archive uniqueness, remove dead columns

- Add missing scheduler_enabled column to global_config (schema drift fix)
- Add unique constraint on inventory_snapshot_history to prevent
  duplicate daily archive rows on re-runs
- Remove unused login_failed_count/login_locked_until from global_config
EOF
)"
```

---

### Task 6: Fix sync_state UPSERT and shop filter bug

**Files:**
- Modify: `backend/app/sync/common.py`
- Modify: `backend/app/sync/order_list.py:101`

- [ ] **Step 1: Rewrite `mark_sync_running` as UPSERT**

Replace the full content of `backend/app/sync/common.py`:

```python
"""同步任务通用工具:sync_state 状态记录。"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_beijing
from app.models.sync_state import SyncState


async def mark_sync_running(db: AsyncSession, job_name: str) -> datetime:
    now = now_beijing()
    stmt = pg_insert(SyncState).values(
        job_name=job_name, last_run_at=now, last_status="running"
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_name"],
        set_={"last_run_at": now, "last_status": "running"},
    )
    await db.execute(stmt)
    await db.commit()
    return now


async def mark_sync_success(db: AsyncSession, job_name: str, started: datetime) -> None:
    now = now_beijing()
    stmt = pg_insert(SyncState).values(
        job_name=job_name,
        last_run_at=started,
        last_success_at=now,
        last_status="success",
        last_error=None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_name"],
        set_={
            "last_run_at": started,
            "last_success_at": now,
            "last_status": "success",
            "last_error": None,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def mark_sync_failed(db: AsyncSession, job_name: str, error: str) -> None:
    stmt = pg_insert(SyncState).values(
        job_name=job_name, last_status="failed", last_error=error[:5000]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_name"],
        set_={"last_status": "failed", "last_error": error[:5000]},
    )
    await db.execute(stmt)
    await db.commit()
```

- [ ] **Step 2: Fix `_resolve_shop_ids` returning None instead of empty list**

In `backend/app/sync/order_list.py`, line 101, change:

```python
# Old:
    return list(rows) if rows else None
# New:
    return list(rows) if rows else []
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/sync/common.py backend/app/sync/order_list.py
git commit -m "$(cat <<'EOF'
fix(sync): use UPSERT for sync_state and fix shop filter returning None

- sync_state now uses INSERT ON CONFLICT DO UPDATE so first-run or
  newly added jobs are tracked correctly instead of silently failing
- _resolve_shop_ids returns [] instead of None when no shops are
  enabled, preventing unintended sync of all shops
EOF
)"
```

---

### Task 7: Fix `list_tasks` total count

**Files:**
- Modify: `backend/app/api/task.py:71-84`

- [ ] **Step 1: Add proper COUNT query**

In `backend/app/api/task.py`, replace the `list_tasks` function (lines 71-84):

```python
@router.get("", response_model=TaskListOut)
async def list_tasks(
    job_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> TaskListOut:
    base = select(TaskRun)
    if job_name:
        base = base.where(TaskRun.job_name == job_name)
    if status:
        base = base.where(TaskRun.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(TaskRun.created_at.desc()).limit(limit))
    ).scalars().all()
    return TaskListOut(items=[TaskRunOut.model_validate(r) for r in rows], total=total)
```

Add `func` import if not present:

```python
from sqlalchemy import func, select, update
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/task.py
git commit -m "$(cat <<'EOF'
fix(api): use proper COUNT query for task list total

Previously total was set to len(rows) which was always <= limit,
producing incorrect pagination metadata.
EOF
)"
```

---

### Task 8: Fix Suggestion PATCH consistency validation

**Files:**
- Modify: `backend/app/api/suggestion.py:152-159`

- [ ] **Step 1: Fix the validation to use effective values**

In `backend/app/api/suggestion.py`, find the consistency check block (around line 152-159) and replace:

```python
# Old:
    # H4:total_qty 与 country_breakdown 一致性
    if (
        patch.total_qty is not None
        and patch.country_breakdown is not None
        and sum(patch.country_breakdown.values()) != patch.total_qty
    ):
        raise ValidationFailed(
            "country_breakdown 之和与 total_qty 不一致"
        )
# New:
    # H4:total_qty 与 country_breakdown 一致性(使用生效值)
    effective_total = patch.total_qty if patch.total_qty is not None else item.total_qty
    effective_breakdown = patch.country_breakdown if patch.country_breakdown is not None else item.country_breakdown
    if effective_breakdown is not None and effective_total is not None:
        if sum(effective_breakdown.values()) != effective_total:
            raise ValidationFailed(
                "country_breakdown 之和与 total_qty 不一致"
            )
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/suggestion.py
git commit -m "$(cat <<'EOF'
fix(api): validate suggestion PATCH consistency using effective values

Previously the total_qty vs country_breakdown check only ran when both
were provided in the same PATCH. Now uses existing values as fallback
to catch inconsistencies when only one field is patched.
EOF
)"
```

---

## Phase 3: Frontend Bug Fixes

### Task 9: Fix TaskProgress polling memory leak

**Files:**
- Modify: `frontend/src/components/TaskProgress.vue:70-78`

- [ ] **Step 1: Stop old polling when taskId changes**

In `frontend/src/components/TaskProgress.vue`, replace the watcher (lines 70-78):

```typescript
// Old:
watch(
  () => props.taskId,
  (id) => {
    if (id) {
      taskStore.startPolling(id, (t) => emit('terminal', t))
    }
  },
  { immediate: true },
)
// New:
watch(
  () => props.taskId,
  (id, oldId) => {
    if (oldId) taskStore.stopPolling(oldId)
    if (id) {
      taskStore.startPolling(id, (t) => emit('terminal', t))
    }
  },
  { immediate: true },
)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TaskProgress.vue
git commit -m "$(cat <<'EOF'
fix(ui): stop old task polling when taskId changes

Previously switching taskId would leave the old task polling
indefinitely until component unmount.
EOF
)"
```

---

### Task 10: Fix WarehouseView save guard

**Files:**
- Modify: `frontend/src/views/WarehouseView.vue:101-109`

- [ ] **Step 1: Remove the ineffective guard**

In `frontend/src/views/WarehouseView.vue`, replace the `save` function (lines 101-110):

```typescript
// Old:
async function save(row: Warehouse, value: string): Promise<void> {
  if (!value || value === row.country) return
  try {
    await patchWarehouseCountry(row.id, value)
    row.country = value
    ElMessage.success(`${row.name} 已更新为 ${value}。`)
  } catch {
    ElMessage.error('更新失败。')
  }
}
// New:
async function save(row: Warehouse, value: string): Promise<void> {
  if (!value) return
  try {
    await patchWarehouseCountry(row.id, value)
    ElMessage.success(`${row.name} 已更新为 ${value}。`)
  } catch {
    ElMessage.error('更新失败。')
    await reload()
  }
}
```

Note: We remove `value === row.country` since `v-model` already mutated `row.country` before `@change` fires. We also reload on error to revert the v-model mutation.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/WarehouseView.vue
git commit -m "$(cat <<'EOF'
fix(ui): fix warehouse save guard that was always skipping API call

v-model mutates row.country before @change fires, so the equality
check was always true. Remove guard and reload on error to revert.
EOF
)"
```

---

### Task 11: Fix SuggestionListView selection not clearing on page change

**Files:**
- Modify: `frontend/src/views/SuggestionListView.vue:149-152`

- [ ] **Step 1: Add page to the watcher**

In `frontend/src/views/SuggestionListView.vue`, line 149, change:

```typescript
// Old:
watch([searchSku, pageSize], () => {
  page.value = 1
  selected.value = []
})
// New:
watch([searchSku, pageSize, page], () => {
  selected.value = []
})
```

Note: We remove `page.value = 1` from inside the watcher since changing `page` itself now triggers it, which would cause an infinite loop. We only need to reset page when `searchSku` or `pageSize` change, not when `page` itself changes. So actually, we should split:

```typescript
// Old:
watch([searchSku, pageSize], () => {
  page.value = 1
  selected.value = []
})
// New:
watch([searchSku, pageSize], () => {
  page.value = 1
  selected.value = []
})
watch(page, () => {
  selected.value = []
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/SuggestionListView.vue
git commit -m "$(cat <<'EOF'
fix(ui): clear selection when changing pages in suggestion list

Prevents stale selections from page 1 being submitted when user
navigates to page 2 and clicks push.
EOF
)"
```

---

### Task 12: Fix DataOrdersView openDetail error handling + ElMessageBox catch

**Files:**
- Modify: `frontend/src/views/data/DataOrdersView.vue:197-205`
- Modify: `frontend/src/views/SuggestionListView.vue` (handlePush)

- [ ] **Step 1: Add error handling to openDetail**

In `frontend/src/views/data/DataOrdersView.vue`, replace lines 197-205:

```typescript
// Old:
async function openDetail(row: DataOrderSummary): Promise<void> {
  const myReqId = ++detailReqId
  dialogVisible.value = true
  detail.value = null
  const data = await getOrderDetail(row.shopId, row.amazonOrderId)
  if (myReqId === detailReqId && dialogVisible.value) {
    detail.value = data
  }
}
// New:
async function openDetail(row: DataOrderSummary): Promise<void> {
  const myReqId = ++detailReqId
  dialogVisible.value = true
  detail.value = null
  try {
    const data = await getOrderDetail(row.shopId, row.amazonOrderId)
    if (myReqId === detailReqId && dialogVisible.value) {
      detail.value = data
    }
  } catch {
    if (myReqId === detailReqId) {
      dialogVisible.value = false
      ElMessage.error('获取订单详情失败')
    }
  }
}
```

- [ ] **Step 2: Catch ElMessageBox cancel in SuggestionListView**

In `frontend/src/views/SuggestionListView.vue`, in the `handlePush` function, wrap the confirm call:

```typescript
// Old (around line 181-185):
  await ElMessageBox.confirm(
    `确认推送 ${selected.value.length} 条建议生成采购单吗？`,
    '确认推送',
    { type: 'warning' },
  )
// New:
  try {
    await ElMessageBox.confirm(
      `确认推送 ${selected.value.length} 条建议生成采购单吗？`,
      '确认推送',
      { type: 'warning' },
    )
  } catch {
    return
  }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/data/DataOrdersView.vue frontend/src/views/SuggestionListView.vue
git commit -m "$(cat <<'EOF'
fix(ui): add error handling for order detail and catch confirm cancel

- openDetail now catches fetch errors and closes dialog with message
- handlePush catches ElMessageBox cancel to prevent unhandled rejection
EOF
)"
```

---

### Task 13: Fix GlobalConfigView cron state after save + syncStatusChart count

**Files:**
- Modify: `frontend/src/views/GlobalConfigView.vue:111-122`
- Modify: `frontend/src/views/WorkspaceView.vue` (syncStatusChartOption)

- [ ] **Step 1: Re-init cron state after save**

In `frontend/src/views/GlobalConfigView.vue`, line 115, add `initCronState()` after successful save:

```typescript
// Old:
    form.value = await patchGlobalConfig(form.value)
    ElMessage.success('已保存')
// New:
    form.value = await patchGlobalConfig(form.value)
    initCronState()
    ElMessage.success('已保存')
```

- [ ] **Step 2: Fix syncStatusChart success counting**

In `frontend/src/views/WorkspaceView.vue`, in the syncStatusChartOption computed, change the success line:

```typescript
// Old:
          { name: '成功', value: counts.success || counts.completed || 0, itemStyle: { color: '#16a34a' } },
// New:
          { name: '成功', value: (counts.success || 0) + (counts.completed || 0), itemStyle: { color: '#16a34a' } },
```

Apply the same fix in `frontend/src/views/SyncConsoleView.vue` if the same pattern exists there.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/GlobalConfigView.vue \
       frontend/src/views/WorkspaceView.vue \
       frontend/src/views/SyncConsoleView.vue
git commit -m "$(cat <<'EOF'
fix(ui): re-init cron state after config save, fix sync status count

- GlobalConfigView: call initCronState() after save to sync dropdown
- WorkspaceView/SyncConsoleView: sum success+completed instead of OR
EOF
)"
```

---

### Task 14: Add 404 catch-all route + fix data view page reset

**Files:**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/views/NotFoundView.vue`
- Modify: `frontend/src/views/data/DataOrdersView.vue`
- Modify: `frontend/src/views/data/DataInventoryView.vue`
- Modify: `frontend/src/views/data/DataOutRecordsView.vue`

- [ ] **Step 1: Create NotFoundView**

Create `frontend/src/views/NotFoundView.vue`:

```vue
<template>
  <div class="not-found">
    <el-empty description="页面不存在">
      <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.not-found {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 50vh;
}
</style>
```

- [ ] **Step 2: Add catch-all route**

In `frontend/src/router/index.ts`, add before the closing `]` of the routes array (before line 147):

```typescript
      { path: 'monitor/overstock', redirect: '/troubleshooting/overstock' },
      // Add this:
      {
        path: ':pathMatch(.*)*',
        name: 'not-found',
        component: () => import('@/views/NotFoundView.vue'),
        meta: { title: '未找到' },
      },
    ],
  },
```

- [ ] **Step 3: Fix data views to reset page on filter change**

In each of these files, add a watcher to reset page when filters change:

**`frontend/src/views/data/DataOrdersView.vue`** — find the `filters` reactive object and add after it:

```typescript
watch(
  () => [filters.sku, filters.country, filters.status],
  () => { page.value = 1 },
)
```

Make sure `watch` is imported from `vue`.

**`frontend/src/views/data/DataInventoryView.vue`** — add similarly:

```typescript
watch(
  () => [filters.sku, filters.country, filters.only_nonzero],
  () => { page.value = 1 },
)
```

**`frontend/src/views/data/DataOutRecordsView.vue`** — add similarly:

```typescript
watch(
  () => [filters.sku, filters.country, filters.is_in_transit],
  () => { page.value = 1 },
)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/NotFoundView.vue frontend/src/router/index.ts \
       frontend/src/views/data/DataOrdersView.vue \
       frontend/src/views/data/DataInventoryView.vue \
       frontend/src/views/data/DataOutRecordsView.vue
git commit -m "$(cat <<'EOF'
fix(ui): add 404 route and reset page on filter change in data views

- Add catch-all route with NotFoundView for unknown paths
- Data views now reset to page 1 when filters change to prevent
  empty table when filtered results have fewer pages
EOF
)"
```

---

## Phase 4: Infrastructure Improvements

### Task 15: DRY docker-compose and fix resource/pool settings

**Files:**
- Modify: `deploy/docker-compose.yml`

- [ ] **Step 1: Refactor docker-compose.yml with YAML anchors**

Replace the full `deploy/docker-compose.yml` with a version using anchors. Key changes:

```yaml
name: restock

x-backend-env: &backend-env
  DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/replenish
  APP_ENV: production
  APP_TIMEZONE: Asia/Shanghai
  APP_LOG_LEVEL: INFO
  SAIHU_BASE_URL: https://openapi.sellfox.com
  SAIHU_CLIENT_ID: ${SAIHU_CLIENT_ID}
  SAIHU_CLIENT_SECRET: ${SAIHU_CLIENT_SECRET}
  LOGIN_PASSWORD: ${LOGIN_PASSWORD}
  JWT_SECRET: ${JWT_SECRET}
  JWT_EXPIRES_HOURS: 24
  TZ: Asia/Shanghai

x-backend-build: &backend-build
  build:
    context: ../backend
    dockerfile: Dockerfile

x-backend-healthcheck: &backend-healthcheck
  healthcheck:
    test:
      [
        "CMD",
        "python",
        "-c",
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz', timeout=2)",
      ]
    interval: 30s
    timeout: 5s
    retries: 5
    start_period: 20s

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: replenish
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      TZ: Asia/Shanghai
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - ./data/pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d replenish"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 1g
    networks:
      - internal

  backend:
    <<: *backend-build
    restart: unless-stopped
    environment:
      <<: *backend-env
      APP_DOCS_ENABLED: ${APP_DOCS_ENABLED:-false}
      PROCESS_ENABLE_WORKER: false
      PROCESS_ENABLE_REAPER: false
      PROCESS_ENABLE_SCHEDULER: false
    depends_on:
      db:
        condition: service_healthy
    <<: *backend-healthcheck
    deploy:
      resources:
        limits:
          memory: 512m
    networks:
      - internal

  worker:
    <<: *backend-build
    restart: unless-stopped
    environment:
      <<: *backend-env
      APP_DOCS_ENABLED: false
      DB_POOL_SIZE: 3
      DB_MAX_OVERFLOW: 2
      PROCESS_ENABLE_WORKER: true
      PROCESS_ENABLE_REAPER: true
      PROCESS_ENABLE_SCHEDULER: false
    depends_on:
      db:
        condition: service_healthy
    <<: *backend-healthcheck
    deploy:
      resources:
        limits:
          memory: 512m
    networks:
      - internal

  scheduler:
    <<: *backend-build
    restart: unless-stopped
    environment:
      <<: *backend-env
      APP_DOCS_ENABLED: false
      DB_POOL_SIZE: 3
      DB_MAX_OVERFLOW: 2
      PROCESS_ENABLE_WORKER: false
      PROCESS_ENABLE_REAPER: false
      PROCESS_ENABLE_SCHEDULER: true
    depends_on:
      db:
        condition: service_healthy
    <<: *backend-healthcheck
    deploy:
      resources:
        limits:
          memory: 512m
    networks:
      - internal

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 256m
    networks:
      - internal

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      APP_DOMAIN: ${APP_DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy:/data
      - ./data/caddy-config:/config
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
    deploy:
      resources:
        limits:
          memory: 128m
    networks:
      - internal

networks:
  internal:
    driver: bridge
```

- [ ] **Step 2: Validate compose file**

Run: `cd /e/Ai_project/restock_system/deploy && docker compose -f docker-compose.yml config > /dev/null`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add deploy/docker-compose.yml
git commit -m "$(cat <<'EOF'
refactor(deploy): DRY docker-compose with YAML anchors, add resource limits

- Extract shared backend env/build/healthcheck into YAML anchors
- Add memory limits to all services
- Reduce pool size for worker/scheduler to 3 (from default 10)
EOF
)"
```

---

### Task 16: Add .dockerignore files and backup retention

**Files:**
- Create: `backend/.dockerignore`
- Create: `frontend/.dockerignore`
- Modify: `deploy/scripts/pg_backup.sh`
- Modify: `deploy/scripts/validate_env.sh:44`

- [ ] **Step 1: Create backend .dockerignore**

Create `backend/.dockerignore`:

```
__pycache__
*.pyc
.env
.env.*
tests/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
.git/
```

- [ ] **Step 2: Create frontend .dockerignore**

Create `frontend/.dockerignore`:

```
node_modules/
dist/
.env
.env.*
*.log
.git/
```

- [ ] **Step 3: Add backup retention to pg_backup.sh**

In `deploy/scripts/pg_backup.sh`, add before the final `echo "[$(date)] done"`:

```bash
# Retain only last 30 days of local backups
find "$BACKUP_DIR" -name "replenish_*.sql.gz" -mtime +30 -delete
echo "[$(date)] cleaned backups older than 30 days"
```

- [ ] **Step 4: Fix validate_env.sh placeholder**

In `deploy/scripts/validate_env.sh`, line 44, change:

```bash
# Old:
if [[ "${LOGIN_PASSWORD}" == "your_initial_login_password" ]]; then
# New:
if [[ "${LOGIN_PASSWORD}" == "please_change_me" ]]; then
```

- [ ] **Step 5: Commit**

```bash
git add backend/.dockerignore frontend/.dockerignore \
       deploy/scripts/pg_backup.sh deploy/scripts/validate_env.sh
git commit -m "$(cat <<'EOF'
chore(deploy): add .dockerignore files, backup retention, fix placeholder

- Exclude tests/node_modules/__pycache__/.env from Docker builds
- Auto-delete backups older than 30 days
- Align LOGIN_PASSWORD placeholder with .env.example
EOF
)"
```

---

### Task 17: Add mypy to CI

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add mypy step to backend CI**

In `.github/workflows/ci.yml`, add after the ruff step:

```yaml
      - name: Run backend type check
        run: python -m mypy app
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
ci: add mypy type checking to backend CI pipeline

The project has strict mypy config in pyproject.toml but CI was not
enforcing it, allowing type regressions to slip through.
EOF
)"
```

---

### Task 18: Improve nonce security in saihu sign

**Files:**
- Modify: `backend/app/saihu/sign.py:48-50`

- [ ] **Step 1: Replace random.randint with secrets**

In `backend/app/saihu/sign.py`, replace the nonce function:

```python
# Old (line 3):
import random
# New:
import secrets

# Old (lines 48-50):
def make_nonce() -> str:
    """每次请求生成的随机 nonce。"""
    return str(random.randint(1, 999999))
# New:
def make_nonce() -> str:
    """每次请求生成的随机 nonce。"""
    return secrets.token_hex(8)
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/saihu/sign.py
git commit -m "$(cat <<'EOF'
fix(security): use cryptographically secure nonce for API signing

Replace random.randint (Mersenne Twister, 6-digit range) with
secrets.token_hex for signing nonces to prevent predictability.
EOF
)"
```

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1 | Tasks 1-4 | Security: CVE fix, injection prevention, redirect, deploy |
| Phase 2 | Tasks 5-8 | Data: schema drift, archive integrity, sync state, validation |
| Phase 3 | Tasks 9-14 | Frontend: polling leak, save bugs, UX improvements |
| Phase 4 | Tasks 15-18 | Infra: Docker DRY, CI, security hardening |

Total: **18 tasks**, each independently committable and testable.
