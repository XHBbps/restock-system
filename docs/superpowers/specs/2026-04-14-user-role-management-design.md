# 用户与角色管理模块设计文档

> **日期**: 2026-04-14
> **状态**: 设计定稿，待实现
> **范围**: 新增多用户认证、角色管理、权限控制（RBAC），替换现有单密码认证体系

---

## 1. 需求概要

为 Restock System 新增用户模块，支持多用户登录、角色分类、细粒度权限控制。

### 1.1 角色模型

- **超级管理员**: 全部权限，系统内置不可编辑/删除
- **阅读者**: 信息总览(查看) + 补货发起(查看) + 历史记录(查看) + 基础数据(查看) + 业务数据(查看)
- **业务人员**: 阅读者权限 + 补货发起(操作) + 历史记录(删除)
- 管理员可创建自定义角色并为其配置权限

### 1.2 用户管理

- 管理员可新增/删除用户、分配角色、重置密码
- 登录方式: 用户名 + 密码
- 默认超管账号: `admin` / `admin123`，不强制改密

### 1.3 前端入口

```
SETTINGS
└── 权限设置（新增二级分组）
    ├── 角色配置
    └── 授权配置
```

---

## 2. 边界保护规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | 至少保留一个超管用户 | 删除/禁用/改角色前检查超管总数 > 1 |
| 2 | 非超管不能给自己提权 | 后端校验操作者权限 |
| 3 | 只有 auth:manage 权限才能操作用户/角色 | 路由级 + API 级双重校验 |
| 4 | 有用户的角色不能删除 | user.role_id FK ON DELETE RESTRICT |
| 5 | 权限修改后立即生效 | perm_version 机制 + 每请求查 user 行 |
| 6 | 不能禁用/删除自己 | 后端校验 current_user.id ≠ target_id |
| 7 | 用户被禁用/删除后立即踢出 | is_active 每请求检查 → 401 |
| 8 | 超管角色不可编辑/删除 | is_superadmin=true 的角色受保护 |
| 9 | 默认超管 admin/admin123 | migration 种子数据，不强制改密 |
| 10 | 权限变更简化审计 | structlog 记录操作日志 |

---

## 3. 数据模型

### 3.1 新增表

```sql
-- 用户表
CREATE TABLE "user" (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    display_name    VARCHAR(50) NOT NULL DEFAULT '',
    password_hash   VARCHAR(128) NOT NULL,
    role_id         INTEGER NOT NULL REFERENCES role(id) ON DELETE RESTRICT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    perm_version    INTEGER NOT NULL DEFAULT 0,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_user_role_id ON "user"(role_id);

-- 角色表
CREATE TABLE role (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) UNIQUE NOT NULL,
    description     VARCHAR(200) DEFAULT '',
    is_superadmin   BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 权限表（由代码注册同步）
CREATE TABLE permission (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    group_name      VARCHAR(50) NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 角色-权限关联表
CREATE TABLE role_permission (
    role_id         INTEGER REFERENCES role(id) ON DELETE CASCADE,
    permission_id   INTEGER REFERENCES permission(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);
```

### 3.2 设计决策

- **user.role_id 单外键**: 角色互斥（不存在一个用户同时是阅读者和业务人员），不用多对多
- **role.is_superadmin**: 超管角色跳过权限检查 + 不可编辑/删除，一个标记解决两个问题
- **permission.sort_order**: 由启动同步逻辑从 REGISTRY 列表 index 自动赋值，不手动维护
- **role_permission.created_at**: 记录权限何时分配，便于排查
- **global_config.login_password_hash**: 保留不删，不影响新逻辑

### 3.3 升级迁移策略

1. Alembic migration 创建 4 张新表
2. 同一 migration 中:
   - 插入权限数据（从代码 REGISTRY 读取）
   - 插入超管角色 (`is_superadmin=true`)
   - 插入阅读者、业务人员默认角色 + 分配对应权限
   - 插入 admin 用户: `username='admin'`, `password_hash=hash('admin123')`, `role_id=超管角色 id`
3. 部署后旧 token 自然失效（`sub` 格式变了），所有用户重新登录

---

## 4. 权限注册表

### 4.1 定义文件: `app/core/permissions.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class PermDef:
    code: str
    name: str
    group_name: str

# ── 权限 code 常量（API 层引用这些做检查）──

HOME_VIEW         = "home:view"
HOME_REFRESH      = "home:refresh"
RESTOCK_VIEW      = "restock:view"
RESTOCK_OPERATE   = "restock:operate"
HISTORY_VIEW      = "history:view"
HISTORY_DELETE    = "history:delete"
DATA_BASE_VIEW    = "data_base:view"
DATA_BASE_EDIT    = "data_base:edit"
DATA_BIZ_VIEW     = "data_biz:view"
SYNC_VIEW         = "sync:view"
SYNC_OPERATE      = "sync:operate"
CONFIG_VIEW       = "config:view"
CONFIG_EDIT       = "config:edit"
MONITOR_VIEW      = "monitor:view"
AUTH_VIEW         = "auth:view"
AUTH_MANAGE       = "auth:manage"

# ── 注册表（列表顺序 = 前端展示顺序）──

REGISTRY: list[PermDef] = [
    PermDef(HOME_VIEW,       "信息总览-查看",   "信息总览"),
    PermDef(HOME_REFRESH,    "信息总览-刷新",   "信息总览"),
    PermDef(RESTOCK_VIEW,    "补货发起-查看",   "补货发起"),
    PermDef(RESTOCK_OPERATE, "补货发起-操作",   "补货发起"),
    PermDef(HISTORY_VIEW,    "历史记录-查看",   "历史记录"),
    PermDef(HISTORY_DELETE,  "历史记录-删除",   "历史记录"),
    PermDef(DATA_BASE_VIEW,  "基础数据-查看",   "基础数据"),
    PermDef(DATA_BASE_EDIT,  "基础数据-编辑",   "基础数据"),
    PermDef(DATA_BIZ_VIEW,   "业务数据-查看",   "业务数据"),
    PermDef(SYNC_VIEW,       "同步管理-查看",   "同步管理"),
    PermDef(SYNC_OPERATE,    "同步管理-操作",   "同步管理"),
    PermDef(CONFIG_VIEW,     "基础配置-查看",   "基础配置"),
    PermDef(CONFIG_EDIT,     "基础配置-编辑",   "基础配置"),
    PermDef(MONITOR_VIEW,    "系统监控-查看",   "系统监控"),
    PermDef(AUTH_VIEW,       "权限设置-查看",   "权限设置"),
    PermDef(AUTH_MANAGE,     "权限设置-管理",   "权限设置"),
]
```

### 4.2 启动同步逻辑

在 `lifespan` 中执行，一个事务内完成：

1. 读取 REGISTRY 中所有 code
2. 查 DB 中已有的 permission 记录
3. 新增的 code → INSERT（sort_order 从 list index 赋值）
4. 已存在的 → 更新 name / group_name / sort_order（如有变化）
5. DB 中有但 REGISTRY 中没有的 → `active=false`
6. 使用 `INSERT ... ON CONFLICT DO UPDATE` 确保并发安全
7. 表不存在时 warning 跳过，不阻塞启动

### 4.3 默认角色权限预设

| 角色 | 权限 codes |
|------|-----------|
| 超级管理员 | 不存 role_permission，`is_superadmin=true` 跳过检查 |
| 阅读者 | `home:view`, `restock:view`, `history:view`, `data_base:view`, `data_biz:view` |
| 业务人员 | 阅读者全部 + `restock:operate`, `history:delete` |

### 4.4 新增权限的流程

1. 开发者在 `permissions.py` 的 REGISTRY 中新增一行
2. API 路由中引用新常量做权限检查
3. 部署重启 → 启动同步自动写入 DB
4. 新权限出现在角色配置页的勾选列表中
5. 超管自动拥有（is_superadmin 跳过检查）
6. 其他角色默认无此权限，管理员按需勾选

---

## 5. 后端鉴权链路

### 5.1 鉴权方案: JWT 认证 + 请求时查库鉴权 + 版本缓存（V4）

**每请求流程:**

```
请求进入
  → JWT 解码（纯内存，HS256 验签）
  → get_current_user: 查 user JOIN role（优化 A，一条 SQL）
    SELECT u.id, u.username, u.display_name, u.is_active,
           u.perm_version, u.role_id, r.is_superadmin, r.name
    FROM "user" u JOIN role r ON u.role_id = r.id
    WHERE u.id = :user_id
  → is_active=false → 401 "账户已被禁用"
  → 无结果 → 401 "用户不存在"
  → get_current_permissions: 版本缓存
    → is_superadmin → ALL_PERMISSIONS，跳过查库
    → 缓存命中且版本匹配 → 直接用（0 额外查询）
    → 缓存未命中 → JOIN 查权限 → 写缓存
  → require_permission: 检查目标权限是否在集合中
    → 不在 → 403 "权限不足"
    → 在 → 放行
```

**稳态性能:** 1 次主键 JOIN 查询 / 请求（~0.05ms）

### 5.2 UserContext

```python
@dataclass
class UserContext:
    id: int
    username: str
    display_name: str
    role_id: int
    role_name: str
    is_superadmin: bool
    perm_version: int
```

### 5.3 权限缓存

```python
class InMemoryPermissionCache:
    """进程内 LRU 权限缓存，版本号驱动失效。"""
    # 结构: dict[user_id, (perm_version, frozenset[str])]
    # maxsize=100（防御性兜底）
    # 单进程安全，无需 Redis

    def get(self, user_id: int, version: int) -> set[str] | None: ...
    def set(self, user_id: int, version: int, perms: set[str]) -> None: ...
    def invalidate(self, user_id: int) -> None: ...
```

### 5.4 缓存失效触发

| 操作 | 触发 SQL（同一事务内） |
|------|---------------------|
| 修改用户角色 | `UPDATE "user" SET perm_version = perm_version + 1 WHERE id = :user_id` |
| 修改角色权限 | `UPDATE "user" SET perm_version = perm_version + 1 WHERE role_id = :role_id` |
| 管理员重置密码 | `UPDATE "user" SET perm_version = perm_version + 1 WHERE id = :user_id`（强制重登） |
| 禁用/删除用户 | 不需要 bump，`get_current_user` 每请求检查 is_active |

### 5.5 异常体系

- `Unauthorized` (401): token 缺失/无效/过期、用户不存在、用户已禁用
- `Forbidden` (403): 已认证但权限不足（新增）

### 5.6 JWT 格式

```json
{
  "sub": "1",          // user_id 字符串形式（JWT RFC 7519）
  "iat": 1713100000,
  "exp": 1713186400
}
```

旧 token `sub="owner"` 无法解析为 int → 自动 401 → 升级过渡自然完成。

### 5.7 路由权限映射

| 端点 | 权限要求 |
|------|---------|
| `POST /api/auth/login` | 公开 |
| `POST /api/auth/logout` | 仅认证 |
| `GET /api/auth/me` | 仅认证 |
| `PUT /api/auth/users/me/password` | 仅认证 |
| `GET /api/auth/users,roles,permissions` | `auth:view` |
| `POST/PUT/DELETE /api/auth/users,roles` | `auth:manage` |
| `PUT /api/auth/users/:id/password` | `auth:manage` |
| `PATCH /api/auth/users/:id/status` | `auth:manage` |
| `PUT /api/auth/roles/:id/permissions` | `auth:manage` |
| `GET /api/metrics/*` | `home:view` |
| `POST /api/metrics/refresh` (未来) | `home:refresh` |
| `GET /api/suggestions` | `restock:view` |
| `POST /api/suggestions/generate` | `restock:operate` |
| `PATCH /api/suggestions/*` | `restock:operate` |
| `POST /api/suggestions/*/push` | `restock:operate` |
| `GET /api/suggestions/history` | `history:view` |
| `DELETE /api/suggestions/*` | `history:delete` |
| `GET /api/data/shops,warehouses,products` | `data_base:view` |
| `PATCH /api/config/sku/*` | `data_base:edit`（注: API 在 config 路由下，权限归基础数据） |
| `GET /api/data/orders,inventory,out-records` | `data_biz:view` |
| `GET /api/sync/*` | `sync:view` |
| `POST /api/sync/*` | `sync:operate` |
| `GET /api/config/*` | `config:view` |
| `PUT /api/config/*` | `config:edit` |
| `GET /api/monitor/*` | `monitor:view` |
| `GET /api/task/*` | 仅认证（基础设施层，不绑业务权限） |

### 5.8 登录 API 响应

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "admin",
    "display_name": "管理员",
    "role_name": "超级管理员",
    "is_superadmin": true,
    "permissions": ["home:view", "home:refresh", "restock:view", ...]
  }
}
```

`/api/auth/me` 返回与 `user` 字段相同的结构（`UserInfoResponse` schema 复用）。

---

## 6. 前端鉴权设计

### 6.1 登录页改造

`LoginView.vue` 增加用户名输入框。提交 `{ username, password }`。

### 6.2 Auth Store 改造

```typescript
// stores/auth.ts
interface UserInfo {
  id: number
  username: string
  displayName: string
  roleName: string
  isSuperadmin: boolean
  permissions: string[]
}

// state: token + user，均持久化到 localStorage
// getters: isAuthenticated, hasPermission(code)
// actions: setAuth(token, user), clearAuth(), restoreAuth()
```

- `hasPermission(code)`: `isSuperadmin || permissions.includes(code)`
- `setAuth`: 同时写 localStorage（token + user JSON）
- `clearAuth`: 同时清 localStorage + state（替代原 clearToken，所有调用点同步更新）
- `restoreAuth`: 路由守卫中首次导航时调 `/api/auth/me` 恢复 user（localStorage 中有快照避免闪烁）

### 6.3 路由守卫

```
beforeEach:
  → meta.public → 放行
  → !token → 跳 /login（带 redirect query）
  → token 存在但 user === null → 调 /api/auth/me 恢复
    → 401 → clearAuth → 跳 /login
  → meta.permission 存在 → hasPermission 检查
    → false → 跳 /403
  → 放行
```

路由 meta.permission 映射：

| 路由 | permission |
|------|-----------|
| `/workspace` | `home:view` |
| `/restock/current` | `restock:view` |
| `/restock/suggestions/:id` | `restock:view` |
| `/restock/history` | `history:view` |
| `/data/shops,warehouses,products` | `data_base:view` |
| `/data/orders,inventory,out-records` | `data_biz:view` |
| `/settings/sync` | `sync:view` |
| `/settings/sync-log` | `sync:view` |
| `/settings/global` | `config:view` |
| `/settings/zipcode` | `config:view` |
| `/settings/api-monitor` | `monitor:view` |
| `/settings/performance` | `monitor:view` |
| `/settings/auth/roles` | `auth:view` |
| `/settings/auth/users` | `auth:view` |
| `/403` | 无（仅认证） |

### 6.4 RouteMeta 类型扩展

```typescript
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    section?: string
    public?: boolean
    permission?: string
  }
}
```

### 6.5 侧边栏菜单过滤

`navigation.ts` 中每个 NavItem / NavSubCategory 新增可选 `permission` 字段。

`AppLayout.vue` 中用 `computed` 生成 `filteredGroups`：
- NavItem: `hasPermission(item.permission)` → 显示/隐藏
- NavSubCategory: 过滤子项 → 无可见子项则隐藏整个分组

新增"权限设置"二级分组：

```typescript
{
  label: '权限设置',
  icon: Shield,
  permission: 'auth:view',
  items: [
    { to: '/settings/auth/roles', label: '角色配置', icon: UserCog, permission: 'auth:view' },
    { to: '/settings/auth/users', label: '授权配置', icon: Users, permission: 'auth:view' },
  ],
},
```

### 6.6 按钮级权限控制

| 页面 | 按钮/操作 | 权限 | 附加约束 |
|------|----------|------|---------|
| 补货发起 | 生成/推送/编辑 | `restock:operate` | 受全局开关约束（disabled + tooltip） |
| 历史记录 | 删除 | `history:delete` | |
| 商品 | SKU 启用/禁用 | `data_base:edit` | |
| 同步控制台 | 手动触发 | `sync:operate` | |
| 全局参数 | 编辑保存 | `config:edit` | |
| 邮编规则 | 增删改 | `config:edit` | |
| 角色配置 | 新建/编辑/删除 | `auth:manage` | |
| 授权配置 | 新建/编辑/删除/重置密码 | `auth:manage` | |
| 信息总览 | 刷新（未来） | `home:refresh` | |

### 6.7 Axios 拦截器

- 401: 保持现有 `window.location.href = '/login'` 模式（避免循环依赖）
- 403: `ElMessage.error('权限不足，请联系管理员')`，不跳转

### 6.8 顶栏用户信息

`AppLayout.vue` topbar-right 新增：
- el-dropdown: 显示 display_name（或 username）
- 下拉菜单: 修改密码（el-dialog）、退出登录

---

## 7. 新增页面

### 7.1 角色配置页 `RoleConfigView.vue`

**路由:** `/settings/auth/roles`

**页面结构:**

```
PageSectionCard title="角色配置"
├── #actions: [新建角色] (需 auth:manage)
└── el-table
    ├── 角色名称
    ├── 描述
    ├── 类型（超管: "系统内置" 标签）
    ├── 用户数（后端 JOIN count）
    └── 操作: 编辑 / 删除
        - 超管角色: 可进入编辑(权限 checkbox disabled), 不可删除
        - 有用户的角色: 不可删除(tooltip 提示)
```

**编辑 Dialog:**

```
el-dialog
├── 角色名称 (el-input, 必填, max 50)
├── 描述 (el-input, 可选, max 200)
└── 权限配置
    ├── 从 GET /api/auth/permissions 获取列表
    ├── 按 group_name 分组，每组一个卡片
    ├── 组内 checkbox 横排
    └── 超管角色: 全选 + disabled + 警示条
```

**API:**

| 操作 | 方法 | 端点 |
|------|------|------|
| 列表 | GET | `/api/auth/roles` |
| 新建 | POST | `/api/auth/roles` |
| 编辑 | PUT | `/api/auth/roles/:id` |
| 删除 | DELETE | `/api/auth/roles/:id` |
| 权限列表 | GET | `/api/auth/permissions` |
| 角色权限查询 | GET | `/api/auth/roles/:id/permissions` |
| 角色权限保存 | PUT | `/api/auth/roles/:id/permissions` |

### 7.2 授权配置页 `UserConfigView.vue`

**路由:** `/settings/auth/users`

**页面结构:**

```
PageSectionCard title="授权配置"
├── #actions: [新建用户] (需 auth:manage)
└── el-table
    ├── 用户名
    ├── 显示名
    ├── 角色 (el-tag)
    ├── 状态 (正常=绿 / 已禁用=红)
    ├── 最后登录
    └── 操作: 编辑 / 重置密码 / 启用禁用 / 删除
```

**边界保护（基于超管用户总数而非特定用户名）:**

| 操作 | 条件 | 行为 |
|------|------|------|
| 禁用/删除超管用户 | 超管总数 > 1 | 允许 |
| 禁用/删除超管用户 | 超管总数 = 1 | disabled，提示"至少需要一个超管" |
| 禁用/删除自己 | — | disabled |
| 变更超管用户角色为非超管 | 超管总数 > 1 | 允许 |
| 变更超管用户角色为非超管 | 超管总数 = 1 | 拒绝 |

**新建用户 Dialog:**

```
el-dialog
├── 用户名 (英文/数字/下划线, max 50)
├── 显示名 (可选, max 50)
├── 密码 (min 6)
├── 确认密码
└── 角色 (el-select)
```

**编辑用户 Dialog:**

```
el-dialog
├── 用户名 (只读)
├── 显示名
└── 角色 (el-select)
```

**重置密码 Dialog:**

```
el-dialog
├── 提示: "将为用户 {username} 设置新密码"
├── 新密码 (min 6)
└── 确认密码
```

**API:**

| 操作 | 方法 | 端点 |
|------|------|------|
| 列表 | GET | `/api/auth/users` |
| 新建 | POST | `/api/auth/users` |
| 编辑 | PUT | `/api/auth/users/:id` |
| 删除 | DELETE | `/api/auth/users/:id` |
| 禁用/启用 | PATCH | `/api/auth/users/:id/status` |
| 重置密码 | PUT | `/api/auth/users/:id/password` |
| 修改自己密码 | PUT | `/api/auth/users/me/password` |

### 7.3 NotAuthorizedView.vue

**路由:** `/403`（layout 内，无 permission 字段）

```vue
<el-empty description="暂无权限访问此页面">
  <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
</el-empty>
```

### 7.4 修改密码 Dialog

位于 `AppLayout.vue` 顶栏下拉菜单，el-dialog 弹出：
- 旧密码 + 新密码 + 确认新密码
- `PUT /api/auth/users/me/password { old_password, new_password }`
- 成功后 clearAuth + 跳登录页

---

## 8. 技术选型

所有实现基于现有技术栈，不引入新依赖：

| 层 | 技术 | 备注 |
|----|------|------|
| 后端鉴权 | FastAPI Depends + JWT (PyJWT) | 现有 |
| 密码哈希 | bcrypt | 现有 |
| ORM | SQLAlchemy 2.0 async | 现有 |
| 迁移 | Alembic | 现有 |
| 前端状态 | Pinia | 现有 |
| 前端 UI | Element Plus | 现有 |
| 前端路由 | Vue Router 4 | 现有 |
| 图标 | lucide-vue-next (Shield, UserCog, Users) | 现有库新增图标 |
