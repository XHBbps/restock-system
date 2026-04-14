# User & Role Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-user authentication with role-based access control (RBAC) to the Restock System, replacing the current single-password login.

**Architecture:** Backend-first approach — build models, permissions, auth chain, then API endpoints. Frontend follows: auth store, login, route guards, new management pages. Each task produces a working, testable commit.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (backend), Vue 3 + Pinia + Element Plus + Vue Router 4 (frontend). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-14-user-role-management-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `app/core/permissions.py` | Permission code constants + REGISTRY + PermDef dataclass |
| `app/core/permission_cache.py` | InMemoryPermissionCache (LRU, version-keyed) |
| `app/core/permission_sync.py` | Startup sync: REGISTRY → DB permission table |
| `app/models/sys_user.py` | SysUser ORM model |
| `app/models/role.py` | Role ORM model |
| `app/models/permission.py` | Permission ORM model |
| `app/models/role_permission.py` | RolePermission ORM model (junction) |
| `app/schemas/auth.py` | Pydantic DTOs: LoginRequest, UserInfoResponse, UserCreate, RoleCreate, etc. |
| `app/api/auth_users.py` | User CRUD API endpoints |
| `app/api/auth_roles.py` | Role CRUD + permission assignment API endpoints |
| `alembic/versions/20260414_2400_add_rbac_tables.py` | Migration: 4 tables + seed data |
| `tests/unit/test_permissions.py` | Permission registry tests |
| `tests/unit/test_permission_cache.py` | Cache tests |
| `tests/unit/test_auth_deps.py` | Auth dependency tests |
| `tests/unit/test_auth_users_api.py` | User API tests |
| `tests/unit/test_auth_roles_api.py` | Role API tests |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `app/core/exceptions.py` | Add `Forbidden(BusinessError)` with status_code=403 |
| `app/core/security.py` | Update `create_access_token` to accept user_id + perm_version |
| `app/api/deps.py` | Replace `get_current_session` with `get_current_user`, add `get_current_permissions`, `require_permission` |
| `app/api/auth.py` | Rewrite login (username+password), rewrite /me, add /me/password |
| `app/models/__init__.py` | Register new models |
| `app/main.py` | Add permission sync + admin seed to lifespan, register new routers |
| `app/api/suggestion.py` | Replace `get_current_session` → `get_current_user` + `require_permission` |
| `app/api/config.py` | Same replacement |
| `app/api/sync.py` | Same replacement |
| `app/api/data.py` | Same replacement |
| `app/api/metrics.py` | Same replacement |
| `app/api/monitor.py` | Same replacement |
| `app/api/task.py` | Replace `get_current_session` → `get_current_user` (no permission required) |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `src/views/RoleConfigView.vue` | Role management page with permission matrix |
| `src/views/UserConfigView.vue` | User management page |
| `src/views/NotAuthorizedView.vue` | 403 page |
| `src/api/auth-management.ts` | API client: user/role CRUD, permissions list |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `src/stores/auth.ts` | Rewrite: token + user, setAuth/clearAuth, hasPermission, restoreAuth |
| `src/api/auth.ts` | Update login (username+password), me response type |
| `src/api/client.ts` | Add 403 interceptor |
| `src/views/LoginView.vue` | Add username field |
| `src/router/index.ts` | RouteMeta extension, permission guard, new routes |
| `src/config/navigation.ts` | Add permission fields, add 权限设置 group |
| `src/components/AppLayout.vue` | filteredGroups computed, topbar user dropdown, password dialog |
| `src/views/SuggestionListView.vue` | v-if permission checks on buttons |
| `src/views/HistoryView.vue` | v-if permission checks on delete |
| `src/views/GlobalConfigView.vue` | v-if permission checks on save |
| `src/views/SyncConsoleView.vue` | v-if permission checks on sync triggers |
| `src/views/data/DataProductsView.vue` | v-if permission checks on SKU toggle |
| `src/views/ZipcodeRuleView.vue` | v-if permission checks on edit |

---

## Task Breakdown

### Task 1: Permission Registry + Exceptions

**Files:**
- Create: `backend/app/core/permissions.py`
- Modify: `backend/app/core/exceptions.py`
- Test: `backend/tests/unit/test_permissions.py`

- [ ] **Step 1: Create `app/core/permissions.py`**

Write the complete file as shown in spec section 4.1. Contains:
- `PermDef` dataclass (frozen, slots)
- 16 permission code constants (HOME_VIEW through AUTH_MANAGE)
- `REGISTRY: list[PermDef]` with all 16 entries
- Helper: `ALL_CODES: frozenset[str] = frozenset(p.code for p in REGISTRY)`

- [ ] **Step 2: Add `Forbidden` exception to `app/core/exceptions.py`**

After the `Unauthorized` class, add:

```python
class Forbidden(BusinessError):  # noqa: N818
    """已认证但权限不足。"""

    status_code = 403
```

- [ ] **Step 3: Register Forbidden handler in `app/main.py`**

The existing `_business_exc_handler` already catches all `BusinessError` subclasses, so `Forbidden` (which extends `BusinessError`) is auto-handled. No code change needed — just verify this by inspection.

- [ ] **Step 4: Write tests for permission registry**

File: `backend/tests/unit/test_permissions.py`

```python
from app.core.permissions import ALL_CODES, REGISTRY, PermDef

def test_registry_not_empty():
    assert len(REGISTRY) >= 16

def test_no_duplicate_codes():
    codes = [p.code for p in REGISTRY]
    assert len(codes) == len(set(codes))

def test_all_codes_match_registry():
    assert ALL_CODES == frozenset(p.code for p in REGISTRY)

def test_permdef_is_frozen():
    p = REGISTRY[0]
    assert isinstance(p, PermDef)
    import pytest
    with pytest.raises(AttributeError):
        p.code = "hack"
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_permissions.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/permissions.py backend/app/core/exceptions.py backend/tests/unit/test_permissions.py
git commit -m "feat(auth): add permission registry and Forbidden exception"
```

---

### Task 2: ORM Models

**Files:**
- Create: `backend/app/models/role.py`
- Create: `backend/app/models/permission.py`
- Create: `backend/app/models/role_permission.py`
- Create: `backend/app/models/sys_user.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create `app/models/role.py`**

```python
"""角色表。"""

from app.db.base import Base, TimestampMixin
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Role(TimestampMixin, Base):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Create `app/models/permission.py`**

```python
"""权限表（由代码注册同步，不手动增删）。"""

from app.db.base import Base, TimestampMixin
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Permission(TimestampMixin, Base):
    __tablename__ = "permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 3: Create `app/models/role_permission.py`**

```python
"""角色-权限关联表。"""

from datetime import datetime

from app.db.base import Base
from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class RolePermission(Base):
    __tablename__ = "role_permission"

    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Create `app/models/sys_user.py`**

```python
"""系统用户表。"""

from datetime import datetime

from app.db.base import Base, TimestampMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class SysUser(TimestampMixin, Base):
    __tablename__ = "sys_user"
    __table_args__ = (Index("ix_sys_user_role_id", "role_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("role.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    perm_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 5: Register models in `app/models/__init__.py`**

Add imports and `__all__` entries for `Role`, `Permission`, `RolePermission`, `SysUser`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/role.py backend/app/models/permission.py \
  backend/app/models/role_permission.py backend/app/models/sys_user.py \
  backend/app/models/__init__.py
git commit -m "feat(auth): add Role, Permission, RolePermission, SysUser ORM models"
```

---

### Task 3: Alembic Migration + Seed Data

**Files:**
- Create: `backend/alembic/versions/20260414_2400_add_rbac_tables.py`

- [ ] **Step 1: Generate migration scaffold**

Run: `cd backend && alembic revision --autogenerate -m "add_rbac_tables" --rev-id 20260414_2400`

- [ ] **Step 2: Edit migration to add seed data**

After the `op.create_table(...)` calls, add seed data in `upgrade()`:

```python
from app.core.permissions import REGISTRY
from app.core.security import hash_password

# Seed permissions
permission_table = sa.table(
    "permission",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("group_name", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("active", sa.Boolean),
)
op.bulk_insert(permission_table, [
    {"code": p.code, "name": p.name, "group_name": p.group_name,
     "sort_order": i, "active": True}
    for i, p in enumerate(REGISTRY)
])

# Seed roles
role_table = sa.table(
    "role",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("is_superadmin", sa.Boolean),
)
op.bulk_insert(role_table, [
    {"id": 1, "name": "超级管理员", "description": "拥有全部权限", "is_superadmin": True},
    {"id": 2, "name": "阅读者", "description": "可查看除系统设置外的所有数据", "is_superadmin": False},
    {"id": 3, "name": "业务人员", "description": "可操作补货发起并查看业务数据", "is_superadmin": False},
])

# Seed role_permission for 阅读者 and 业务人员
# Query permission IDs by code using a bind connection
conn = op.get_bind()
perm_rows = conn.execute(sa.text("SELECT id, code FROM permission")).fetchall()
code_to_id = {row.code: row.id for row in perm_rows}

viewer_codes = ["home:view", "restock:view", "history:view", "data_base:view", "data_biz:view"]
operator_codes = viewer_codes + ["restock:operate", "history:delete"]

rp_table = sa.table(
    "role_permission",
    sa.column("role_id", sa.Integer),
    sa.column("permission_id", sa.Integer),
)
rp_rows = []
for code in viewer_codes:
    rp_rows.append({"role_id": 2, "permission_id": code_to_id[code]})
for code in operator_codes:
    rp_rows.append({"role_id": 3, "permission_id": code_to_id[code]})
op.bulk_insert(rp_table, rp_rows)

# Seed admin user
user_table = sa.table(
    "sys_user",
    sa.column("username", sa.String),
    sa.column("display_name", sa.String),
    sa.column("password_hash", sa.String),
    sa.column("role_id", sa.Integer),
    sa.column("is_active", sa.Boolean),
    sa.column("perm_version", sa.Integer),
)
op.bulk_insert(user_table, [
    {
        "username": "admin",
        "display_name": "管理员",
        "password_hash": hash_password("admin123"),
        "role_id": 1,
        "is_active": True,
        "perm_version": 0,
    }
])
```

Also add a comment to global_config deprecating the login_password_hash field:
```python
# Note: global_config.login_password_hash is DEPRECATED, replaced by sys_user.password_hash
# Field retained for backward compatibility; login endpoint ignores it.
```

- [ ] **Step 3: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Tables created, seed data inserted without error.

- [ ] **Step 4: Verify seed data**

Run: `cd backend && python -c "
import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text
async def check():
    async with async_session_factory() as db:
        users = (await db.execute(text('SELECT username, role_id FROM sys_user'))).fetchall()
        roles = (await db.execute(text('SELECT id, name FROM role'))).fetchall()
        perms = (await db.execute(text('SELECT count(*) FROM permission'))).scalar()
        print(f'Users: {users}')
        print(f'Roles: {roles}')
        print(f'Permissions: {perms}')
asyncio.run(check())
"`
Expected: 1 user (admin), 3 roles, 16 permissions.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260414_2400_add_rbac_tables.py
git commit -m "feat(auth): add RBAC migration with seed data"
```

---

### Task 4: Permission Cache + Sync

**Files:**
- Create: `backend/app/core/permission_cache.py`
- Create: `backend/app/core/permission_sync.py`
- Test: `backend/tests/unit/test_permission_cache.py`

- [ ] **Step 1: Create `app/core/permission_cache.py`**

```python
"""进程内 LRU 权限缓存，版本号驱动失效。"""

from collections import OrderedDict


class InMemoryPermissionCache:
    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[int, tuple[int, frozenset[str]]] = OrderedDict()

    def get(self, user_id: int, version: int) -> frozenset[str] | None:
        entry = self._store.get(user_id)
        if entry is None:
            return None
        cached_version, perms = entry
        if cached_version != version:
            return None
        self._store.move_to_end(user_id)
        return perms

    def set(self, user_id: int, version: int, perms: frozenset[str]) -> None:
        self._store[user_id] = (version, perms)
        self._store.move_to_end(user_id)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def invalidate(self, user_id: int) -> None:
        self._store.pop(user_id, None)

    def clear(self) -> None:
        self._store.clear()


# Singleton instance used by auth dependencies
perm_cache = InMemoryPermissionCache()
```

- [ ] **Step 2: Write cache tests**

File: `backend/tests/unit/test_permission_cache.py`

```python
from app.core.permission_cache import InMemoryPermissionCache

def test_cache_miss_returns_none():
    cache = InMemoryPermissionCache()
    assert cache.get(1, 0) is None

def test_cache_hit_returns_perms():
    cache = InMemoryPermissionCache()
    perms = frozenset({"home:view", "restock:view"})
    cache.set(1, 0, perms)
    assert cache.get(1, 0) == perms

def test_version_mismatch_returns_none():
    cache = InMemoryPermissionCache()
    cache.set(1, 0, frozenset({"home:view"}))
    assert cache.get(1, 1) is None

def test_invalidate_removes_entry():
    cache = InMemoryPermissionCache()
    cache.set(1, 0, frozenset({"home:view"}))
    cache.invalidate(1)
    assert cache.get(1, 0) is None

def test_lru_eviction():
    cache = InMemoryPermissionCache(maxsize=2)
    cache.set(1, 0, frozenset())
    cache.set(2, 0, frozenset())
    cache.set(3, 0, frozenset())  # evicts user 1
    assert cache.get(1, 0) is None
    assert cache.get(2, 0) is not None
    assert cache.get(3, 0) is not None
```

- [ ] **Step 3: Run cache tests**

Run: `cd backend && python -m pytest tests/unit/test_permission_cache.py -v`
Expected: 5 PASS

- [ ] **Step 4: Create `app/core/permission_sync.py`**

```python
"""启动时权限注册表同步到 DB。"""

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import REGISTRY
from app.models.permission import Permission

logger = get_logger(__name__)


async def sync_permissions(db: AsyncSession) -> None:
    """将 REGISTRY 同步到 permission 表，幂等可重入。"""
    try:
        existing = {
            row.code: row
            for row in (await db.execute(select(Permission))).scalars().all()
        }
    except Exception:
        logger.warning("permission_sync_skipped", reason="permission table does not exist yet")
        return

    registry_codes = set()
    for idx, perm_def in enumerate(REGISTRY):
        registry_codes.add(perm_def.code)
        stmt = pg_insert(Permission).values(
            code=perm_def.code,
            name=perm_def.name,
            group_name=perm_def.group_name,
            sort_order=idx,
            active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Permission.code],
            set_={
                "name": perm_def.name,
                "group_name": perm_def.group_name,
                "sort_order": idx,
                "active": True,
            },
        )
        await db.execute(stmt)

    # Mark removed permissions as inactive
    for code, row in existing.items():
        if code not in registry_codes and row.active:
            await db.execute(
                update(Permission)
                .where(Permission.code == code)
                .values(active=False)
            )
            logger.info("permission_deactivated", code=code)

    await db.commit()
    logger.info("permission_sync_complete", total=len(REGISTRY))
```

- [ ] **Step 5: Add sync call to `app/main.py` lifespan**

In the `lifespan` function, after `await _ensure_global_config()`, add:

```python
from app.core.permission_sync import sync_permissions

# inside lifespan, after _ensure_global_config:
async with async_session_factory() as db:
    await sync_permissions(db)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/permission_cache.py backend/app/core/permission_sync.py \
  backend/tests/unit/test_permission_cache.py backend/app/main.py
git commit -m "feat(auth): add permission cache and startup sync"
```

---

### Task 5: Auth Dependencies (Core Auth Chain)

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/unit/test_auth_deps.py`

- [ ] **Step 1: Update `app/core/security.py`**

Modify `create_access_token` to accept `user_id: int` and `perm_version: int`:

```python
def create_access_token(user_id: int, perm_version: int = 0) -> str:
    """签发 JWT，payload 包含 user_id (sub) 和 perm_version (pv)。"""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.jwt_expires_hours)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "pv": perm_version,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
```

Remove the old `subject: str = "owner"` parameter and `extra` parameter.

- [ ] **Step 2: Rewrite `app/api/deps.py`**

Replace entire file with new auth dependencies:

```python
"""FastAPI 通用依赖。"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, Unauthorized
from app.core.permission_cache import perm_cache
from app.core.permissions import ALL_CODES
from app.core.security import decode_token
from app.db.session import get_db
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.sys_user import SysUser


@dataclass
class UserContext:
    id: int
    username: str
    display_name: str
    role_id: int
    role_name: str
    is_superadmin: bool
    perm_version: int


# 同步会话依赖
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


_ALL_PERMISSIONS = frozenset(ALL_CODES)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(db_session),
) -> UserContext:
    """从 JWT 中取出 user_id，查库验证用户状态和 perm_version。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("缺少 Authorization Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if "sub" not in payload:
        raise Unauthorized("token 缺少 subject")

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise Unauthorized("token 无效")

    token_pv = payload.get("pv", -1)

    row = (
        await db.execute(
            select(
                SysUser.id,
                SysUser.username,
                SysUser.display_name,
                SysUser.is_active,
                SysUser.perm_version,
                SysUser.role_id,
                Role.is_superadmin,
                Role.name.label("role_name"),
            )
            .join(Role, SysUser.role_id == Role.id)
            .where(SysUser.id == user_id)
        )
    ).first()

    if row is None:
        raise Unauthorized("用户不存在")
    if not row.is_active:
        raise Unauthorized("账户已被禁用")
    if row.perm_version != token_pv:
        raise Unauthorized("会话已过期，请重新登录")

    return UserContext(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        role_id=row.role_id,
        role_name=row.role_name,
        is_superadmin=row.is_superadmin,
        perm_version=row.perm_version,
    )


async def get_current_permissions(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> frozenset[str]:
    """返回当前用户的权限 code 集合，超管返回全量。"""
    if user.is_superadmin:
        return _ALL_PERMISSIONS

    cached = perm_cache.get(user.id, user.perm_version)
    if cached is not None:
        return cached

    rows = (
        await db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == user.role_id, Permission.active.is_(True))
        )
    ).scalars().all()

    perms = frozenset(rows)
    perm_cache.set(user.id, user.perm_version, perms)
    return perms


def require_permission(*codes: str):
    """路由级权限检查工厂（AND 语义：所有 codes 必须满足）。"""
    async def _checker(
        permissions: frozenset[str] = Depends(get_current_permissions),
    ) -> None:
        for code in codes:
            if code not in permissions:
                raise Forbidden("权限不足")
    return _checker


__all__ = [
    "Depends",
    "UserContext",
    "db_session",
    "get_current_permissions",
    "get_current_user",
    "require_permission",
]
```

- [ ] **Step 3: Write auth dependency tests**

File: `backend/tests/unit/test_auth_deps.py`

Test at minimum:
- `get_current_user` with missing auth header → Unauthorized
- `get_current_user` with invalid token → Unauthorized
- `require_permission` with missing permission → Forbidden
- Permission cache hit path (mock DB)
- Superadmin bypasses permission check

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_auth_deps.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/app/api/deps.py \
  backend/tests/unit/test_auth_deps.py
git commit -m "feat(auth): add get_current_user, get_current_permissions, require_permission deps"
```

---

### Task 6: Auth Schemas

**Files:**
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: Create `app/schemas/auth.py`**

```python
"""认证与用户管理 Pydantic DTO。"""

from pydantic import BaseModel, Field


# ── Login ──

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserInfoResponse(BaseModel):
    id: int
    username: str
    display_name: str = Field(alias="display_name")
    role_name: str
    is_superadmin: bool
    password_is_default: bool
    permissions: list[str]

    model_config = {"from_attributes": True, "populate_by_name": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoResponse


# ── User CRUD ──

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(default="", max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role_id: int


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=50)
    role_id: int | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role_id: int
    role_name: str
    is_active: bool
    is_superadmin: bool
    last_login_at: str | None = None

    model_config = {"from_attributes": True}


class UserStatusPatch(BaseModel):
    is_active: bool


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class ChangeOwnPassword(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


# ── Role CRUD ──

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    is_superadmin: bool
    user_count: int = 0

    model_config = {"from_attributes": True}


class RolePermissionUpdate(BaseModel):
    permission_codes: list[str]


# ── Permission list ──

class PermissionOut(BaseModel):
    code: str
    name: str
    group_name: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/auth.py
git commit -m "feat(auth): add auth Pydantic schemas"
```

---

### Task 7: Rewrite Login + /me + /me/password API

**Files:**
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/unit/test_auth_login.py` (update existing)

- [ ] **Step 1: Rewrite `app/api/auth.py`**

Major changes:
- Login: accept `{ username, password }` → query `sys_user` by username → verify password → dual-dimension login_attempt tracking (ip + user) → create JWT with `user_id` + `perm_version` → return LoginResponse with user info + permissions → update `last_login_at`
- `/me`: query user + role + permissions → return `UserInfoResponse` (reuse `_build_user_info` helper)
- `/me/password`: verify old_password → hash new_password → update → clearAuth on client
- `/logout`: keep as-is (stateless, just returns 204)
- `password_is_default`: compare `verify_password("admin123", user.password_hash)`

Helper function `_build_user_info(db, user_row)` that loads permissions and returns `UserInfoResponse` — used by both login and /me.

**Route registration order (critical):** Define `/users/me/password` BEFORE any `/{user_id}` routes. In this file, `/me/password` is part of the auth router, not the users CRUD router, so it naturally comes first.

- [ ] **Step 2: Update existing login tests**

Update `tests/unit/test_auth_login.py` to use `{ username, password }` instead of `{ password }`.

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_auth_login.py -v`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/auth.py backend/tests/unit/test_auth_login.py
git commit -m "feat(auth): rewrite login for multi-user, add /me and /me/password"
```

---

### Task 8: User Management API

**Files:**
- Create: `backend/app/api/auth_users.py`
- Test: `backend/tests/unit/test_auth_users_api.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create `app/api/auth_users.py`**

Endpoints (all prefixed `/api/auth/users`):
- `GET /` → list users (JOIN role for role_name, is_superadmin; include user_count)
- `POST /` → create user (validate unique username, hash password, check role exists)
- `PUT /{user_id}` → update user (display_name, role_id; boundary checks for last superadmin)
- `DELETE /{user_id}` → delete user (boundary: can't delete self, last superadmin check)
- `PATCH /{user_id}/status` → toggle is_active (boundary: can't disable self, last superadmin)
- `PUT /{user_id}/password` → reset password (bump perm_version)

All write endpoints:
- Require `auth:manage` via `Depends(require_permission(AUTH_MANAGE))`
- Log audit events via structlog
- Bump `perm_version` where specified in spec section 5.4

Boundary check helper `_check_last_superadmin(db, user_id)`: count sys_user where role.is_superadmin AND is_active AND id != user_id. If 0, raise BusinessError.

- [ ] **Step 2: Register router in `app/main.py`**

```python
from app.api import auth_users as auth_users_api
app.include_router(auth_users_api.router)
```

- [ ] **Step 3: Write API tests**

File: `backend/tests/unit/test_auth_users_api.py`

Cover at minimum:
- List users returns admin
- Create user with valid data succeeds
- Create user with duplicate username → 409
- Delete self → 400
- Delete last superadmin → 400
- Disable self → 400
- Password reset bumps perm_version

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_auth_users_api.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/auth_users.py backend/tests/unit/test_auth_users_api.py backend/app/main.py
git commit -m "feat(auth): add user management API with boundary protection"
```

---

### Task 9: Role Management API

**Files:**
- Create: `backend/app/api/auth_roles.py`
- Test: `backend/tests/unit/test_auth_roles_api.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create `app/api/auth_roles.py`**

Endpoints (all prefixed `/api/auth`):
- `GET /roles` → list roles (with user_count via subquery)
- `POST /roles` → create role
- `PUT /roles/{role_id}` → update role (block if is_superadmin)
- `DELETE /roles/{role_id}` → delete role (block if is_superadmin or has users)
- `GET /roles/{role_id}/permissions` → list permission codes for role
- `PUT /roles/{role_id}/permissions` → replace permissions (accept `permission_codes[]`, resolve to IDs, replace role_permission rows, bump perm_version for affected users)
- `GET /permissions` → list all active permissions (from REGISTRY order via sort_order)

All write endpoints require `auth:manage`. Read endpoints require `auth:view`.

- [ ] **Step 2: Register router in `app/main.py`**

```python
from app.api import auth_roles as auth_roles_api
app.include_router(auth_roles_api.router)
```

- [ ] **Step 3: Write API tests**

Cover:
- List roles returns 3 defaults
- Create custom role succeeds
- Delete superadmin role → 400
- Delete role with users → 400 (FK RESTRICT)
- Update role permissions + verify perm_version bumped
- GET /permissions returns all 16 entries in order

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_auth_roles_api.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/auth_roles.py backend/tests/unit/test_auth_roles_api.py backend/app/main.py
git commit -m "feat(auth): add role management API with permission assignment"
```

---

### Task 10: Apply Permissions to Existing Routes

**Files:**
- Modify: `backend/app/api/suggestion.py`
- Modify: `backend/app/api/config.py`
- Modify: `backend/app/api/sync.py`
- Modify: `backend/app/api/data.py`
- Modify: `backend/app/api/metrics.py`
- Modify: `backend/app/api/monitor.py`
- Modify: `backend/app/api/task.py`

- [ ] **Step 1: Replace `get_current_session` with `get_current_user` + `require_permission` in all API files**

Pattern for each file — find-replace:

```python
# Before:
from app.api.deps import db_session, get_current_session
# ...
session: dict[str, Any] = Depends(get_current_session),

# After:
from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.core.permissions import RESTOCK_VIEW  # (appropriate constant)
# ...
user: UserContext = Depends(get_current_user),
_: None = Depends(require_permission(RESTOCK_VIEW)),
```

Apply per spec section 5.7 route permission mapping. For `task.py`, only replace with `get_current_user` (no require_permission).

- [ ] **Step 2: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All existing tests pass (may need minor fixture updates for the new auth format).

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/suggestion.py backend/app/api/config.py \
  backend/app/api/sync.py backend/app/api/data.py backend/app/api/metrics.py \
  backend/app/api/monitor.py backend/app/api/task.py
git commit -m "feat(auth): apply require_permission to all existing API routes"
```

---

### Task 11: Frontend Auth Store + API Client

**Files:**
- Modify: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth-management.ts`

- [ ] **Step 1: Rewrite `src/stores/auth.ts`**

Replace with new store that has:
- `token: ref<string | null>` (from localStorage)
- `user: ref<UserInfo | null>` (from localStorage)
- `isAuthenticated: computed`
- `hasPermission(code: string): boolean` method
- `setAuth(token, user)`, `clearAuth()`
- `restoreAuth()` with Promise dedup pattern
- Both `token` and `user` persisted to localStorage on set/clear

- [ ] **Step 2: Update `src/api/auth.ts`**

- `login(username, password)` → returns `LoginResponse` (with user field)
- `me()` → returns `UserInfoResponse`
- `changeOwnPassword(oldPassword, newPassword)` → PUT /api/auth/users/me/password
- Update interfaces to match backend schemas

- [ ] **Step 3: Update `src/api/client.ts`**

- Change `auth.clearToken()` → `auth.clearAuth()`
- Add 403 handler:

```typescript
if (error.response?.status === 403) {
  ElMessage.error('权限不足，请联系管理员')
  // Trigger permission refresh
  const auth = useAuthStore()
  auth.restoreAuth()
}
```

- [ ] **Step 4: Create `src/api/auth-management.ts`**

API client for user/role management:
- `getUsers()`, `createUser()`, `updateUser()`, `deleteUser()`, `toggleUserStatus()`, `resetPassword()`
- `getRoles()`, `createRole()`, `updateRole()`, `deleteRole()`
- `getPermissions()`, `getRolePermissions()`, `updateRolePermissions()`

- [ ] **Step 5: Update auth store tests**

Update `src/stores/__tests__/auth.test.ts` for new setAuth/clearAuth API.

- [ ] **Step 6: Run frontend type check**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/auth.ts frontend/src/api/auth.ts \
  frontend/src/api/client.ts frontend/src/api/auth-management.ts \
  frontend/src/stores/__tests__/auth.test.ts
git commit -m "feat(auth): rewrite frontend auth store, API client, 403 handling"
```

---

### Task 12: Frontend Login + Route Guards + Navigation

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/config/navigation.ts`
- Create: `frontend/src/views/NotAuthorizedView.vue`

- [ ] **Step 1: Update `LoginView.vue`**

- Add username `el-input` field above password field
- Update `handleLogin` to call `login(username, password)`
- After login success: `auth.setAuth(resp.access_token, resp.user)`
- Add default password notification:

```typescript
if (resp.user.password_is_default) {
  ElNotification({ title: '安全提醒', message: '当前使用默认密码，建议尽快修改', type: 'warning', duration: 8000 })
}
```

- [ ] **Step 2: Create `NotAuthorizedView.vue`**

```vue
<template>
  <div class="not-authorized">
    <el-empty description="暂无权限访问此页面">
      <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.not-authorized {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 50vh;
}
</style>
```

- [ ] **Step 3: Update `router/index.ts`**

- Add RouteMeta type extension (permission field)
- Add `permission` to each route's meta per spec section 6.3 mapping
- Add `/403` route and `/settings/auth/roles`, `/settings/auth/users` routes
- Rewrite `authGuard` to include permission checking and restoreAuth:

```typescript
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }

  // Restore user if needed (page refresh)
  if (!auth.user) {
    try {
      await auth.restoreAuth()
    } catch {
      auth.clearAuth()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  // Permission check
  const required = to.meta.permission as string | undefined
  if (required && !auth.hasPermission(required)) {
    return { path: '/403' }
  }

  return true
})
```

- [ ] **Step 4: Update `config/navigation.ts`**

- Add `permission?: string` to `NavItem` and `NavSubCategory` interfaces
- Add `permission` field to every navigation item per spec section 6.7
- Add new "权限设置" subcategory with Shield, UserCog, Users icons
- Import new icons: `Shield, UserCog, Users` from lucide-vue-next

- [ ] **Step 5: Run type check**

Run: `cd frontend && npx vue-tsc --noEmit`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/views/NotAuthorizedView.vue \
  frontend/src/router/index.ts frontend/src/config/navigation.ts
git commit -m "feat(auth): update login page, add route guards with permissions, navigation filtering"
```

---

### Task 13: AppLayout Changes (Sidebar Filtering + Topbar + Password Dialog)

**Files:**
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: Add sidebar filtering with `filteredGroups` computed**

```typescript
const auth = useAuthStore()

const filteredGroups = computed(() => {
  return navigationGroups
    .map(group => ({
      ...group,
      children: group.children
        .filter(child => {
          if (isSubCategory(child)) {
            return child.items.some(item => !item.permission || auth.hasPermission(item.permission))
          }
          return !child.permission || auth.hasPermission(child.permission)
        })
        .map(child => {
          if (isSubCategory(child)) {
            return {
              ...child,
              items: child.items.filter(item => !item.permission || auth.hasPermission(item.permission)),
            }
          }
          return child
        }),
    }))
    .filter(group => group.children.length > 0)
})
```

Replace `navigationGroups` with `filteredGroups` in template.

- [ ] **Step 2: Add topbar user dropdown**

In `topbar-right`, add:

```vue
<el-dropdown @command="handleUserCommand">
  <span class="user-dropdown-trigger">
    {{ auth.user?.displayName || auth.user?.username || '' }}
    <ChevronDown :size="14" />
  </span>
  <template #dropdown>
    <el-dropdown-menu>
      <el-dropdown-item command="change-password">修改密码</el-dropdown-item>
      <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
    </el-dropdown-menu>
  </template>
</el-dropdown>
```

- [ ] **Step 3: Add password change dialog**

Add `el-dialog` with old_password, new_password, confirm_password fields.
On submit: `PUT /api/auth/users/me/password` → success → `auth.clearAuth()` → redirect to login.

- [ ] **Step 4: Move logout logic into `handleUserCommand`**

```typescript
async function handleUserCommand(cmd: string) {
  if (cmd === 'logout') await handleLogout()
  if (cmd === 'change-password') showPasswordDialog.value = true
}
```

- [ ] **Step 5: Run type check + dev server visual test**

Run: `cd frontend && npx vue-tsc --noEmit`
Start dev server, verify sidebar filtering works for different permission sets.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "feat(auth): add sidebar permission filtering, topbar user menu, password change dialog"
```

---

### Task 14: Role Config Page

**Files:**
- Create: `frontend/src/views/RoleConfigView.vue`

- [ ] **Step 1: Build RoleConfigView.vue**

Structure:
- `PageSectionCard` with title "角色配置"
- Action button: "新建角色" (v-if `auth.hasPermission('auth:manage')`)
- `el-table` with columns: name, description, type tag, user_count, actions
- Edit dialog with role name + description + permission checkbox matrix
- Permission matrix: fetch from `GET /api/auth/permissions`, group by `group_name`, render checkboxes
- Each group has a "全选" checkbox in header
- Superadmin role: all checkboxes checked + disabled + alert banner
- Delete confirmation with protection checks

Follow existing page patterns (PageSectionCard, el-table, el-dialog) from SuggestionListView and GlobalConfigView.

- [ ] **Step 2: Run type check**

Run: `cd frontend && npx vue-tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/RoleConfigView.vue
git commit -m "feat(auth): add role configuration page with permission matrix"
```

---

### Task 15: User Config Page

**Files:**
- Create: `frontend/src/views/UserConfigView.vue`

- [ ] **Step 1: Build UserConfigView.vue**

Structure:
- `PageSectionCard` with title "授权配置"
- Action button: "新建用户"
- `el-table`: username, display_name, role (el-tag), status (el-tag), last_login_at, actions
- Create dialog: username, display_name, password, confirm_password, role select
- Edit dialog: username (readonly), display_name, role select
- Reset password dialog: new_password, confirm_password
- Action buttons with boundary protection:
  - Compute `superadminCount` from user list
  - Disable delete/disable for self (`user.id === auth.user.id`)
  - Disable delete/disable for last superadmin

- [ ] **Step 2: Run type check**

Run: `cd frontend && npx vue-tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/UserConfigView.vue
git commit -m "feat(auth): add user configuration page with boundary protection"
```

---

### Task 16: Apply Button-Level Permissions to Existing Pages

**Files:**
- Modify: `frontend/src/views/SuggestionListView.vue`
- Modify: `frontend/src/views/HistoryView.vue`
- Modify: `frontend/src/views/GlobalConfigView.vue`
- Modify: `frontend/src/views/SyncConsoleView.vue`
- Modify: `frontend/src/views/data/DataProductsView.vue`
- Modify: `frontend/src/views/ZipcodeRuleView.vue`

- [ ] **Step 1: Add permission checks to each page**

Pattern for each file:

```typescript
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
```

Then wrap action buttons:

| Page | Button | Guard |
|------|--------|-------|
| SuggestionListView | 生成补货建议, 推送 | `v-if="auth.hasPermission('restock:operate')"` |
| HistoryView | 删除 | `v-if="auth.hasPermission('history:delete')"` |
| GlobalConfigView | 保存 | `v-if="auth.hasPermission('config:edit')"` |
| SyncConsoleView | 手动同步 buttons | `v-if="auth.hasPermission('sync:operate')"` |
| DataProductsView | SKU 开关 | `v-if="auth.hasPermission('data_base:edit')"` |
| ZipcodeRuleView | 增删改 buttons | `v-if="auth.hasPermission('config:edit')"` |

- [ ] **Step 2: Run type check + build**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/SuggestionListView.vue frontend/src/views/HistoryView.vue \
  frontend/src/views/GlobalConfigView.vue frontend/src/views/SyncConsoleView.vue \
  frontend/src/views/data/DataProductsView.vue frontend/src/views/ZipcodeRuleView.vue
git commit -m "feat(auth): apply button-level permission checks to existing pages"
```

---

### Task 17: Integration Test + Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests pass.

- [ ] **Step 2: Run full frontend checks**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build && npx vitest run`
Expected: Type check, build, and tests all pass.

- [ ] **Step 3: Manual smoke test**

Start both backend and frontend dev servers:
1. Login as admin/admin123 → verify default password notification
2. Create a "viewer" role with only read permissions
3. Create a test user with viewer role
4. Login as test user → verify:
   - Sidebar only shows permitted pages
   - Action buttons hidden on read-only pages
   - Direct URL to /settings/global → redirects to /403
5. As admin, change test user's role → test user gets 401 on next action → re-login shows new permissions

- [ ] **Step 4: Update docs/PROGRESS.md**

Add entry for RBAC module completion.

- [ ] **Step 5: Final commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs: update progress with RBAC module completion"
```
