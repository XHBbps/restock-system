# Restock System 全面审查清单

> 审查日期：2026-04-14
> 审查视角：资深架构师 + 高级前端工程师 + 高级后端工程师 + 资深运维
> 目标：输出可执行的审查清单，后续修改交给 Codex 执行
> 原则：优先功能优化，最后完善部署；在不影响功能的情况下修复

---

## 目录

1. [阻塞级问题（BLOCKING）](#1-阻塞级问题blocking)
2. [安全问题（SECURITY）](#2-安全问题security)
3. [性能问题（PERFORMANCE）](#3-性能问题performance)
4. [健壮性问题（ROBUSTNESS）](#4-健壮性问题robustness)
5. [错误处理缺口（ERROR HANDLING）](#5-错误处理缺口error-handling)
6. [类型安全与代码质量（CODE QUALITY）](#6-类型安全与代码质量code-quality)
7. [扩展性问题（SCALABILITY）](#7-扩展性问题scalability)
8. [部署与运维优化（DEPLOYMENT）](#8-部署与运维优化deployment)
9. [CI/CD 完善（CI/CD）](#9-cicd-完善cicd)
10. [监控与可观测性（OBSERVABILITY）](#10-监控与可观测性observability)
11. [项目优点总结](#11-项目优点总结)

---

## 1. 阻塞级问题（BLOCKING）

这些问题会在生产环境中导致服务不可用或数据丢失，必须在部署前修复。

### B-01: 后端缺少通用 500 错误处理器

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/main.py` |
| 行号 | 124-142 |
| 严重程度 | 高 |
| 影响 | 未处理的异常（`ValueError`、`RuntimeError`、数据库连接失败等）会返回 FastAPI 默认的 500 响应，**堆栈跟踪会暴露给客户端**，泄露内部实现细节 |

**修复方案**：

在 `main.py` 中添加通用异常处理器：

```python
# backend/app/main.py — 在现有 exception_handler 之后添加
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )
```

- 不影响 `BusinessError` 和 `SaihuAPIError` 的已有处理
- 日志中记录完整异常栈，但对客户端只返回通用消息

---

### B-02: 数据库引擎未在 shutdown 时关闭

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/main.py`, `backend/app/db/session.py` |
| 行号 | main.py:97-107 |
| 严重程度 | 高 |
| 影响 | 应用关闭时连接池未被清理，连接泄漏。在部署更新频繁的场景下，可能耗尽 PostgreSQL 连接数 |

**修复方案**：

```python
# backend/app/main.py — lifespan shutdown 部分
from app.db.session import engine

# 在 shutdown 阶段末尾添加
await engine.dispose()
logger.info("database_engine_disposed")
```

---

### B-03: SaihuClient httpx 连接未在 shutdown 时关闭

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/saihu/client.py`, `backend/app/main.py` |
| 严重程度 | 中高 |
| 影响 | httpx AsyncClient 未显式关闭，留下悬挂的 HTTP 连接 |

**修复方案**：

```python
# backend/app/main.py — lifespan shutdown 部分
from app.saihu.client import get_saihu_client

client = get_saihu_client()
await client.aclose()  # 或者在 SaihuClient 上提供一个 close() 方法
logger.info("saihu_client_closed")
```

---

### B-04: `InventorySnapshotHistory` ORM 模型缺少唯一约束声明

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/models/inventory.py` |
| 行号 | 46-62 |
| 严重程度 | 中高 |
| 影响 | `daily_archive` 任务依赖 `(commodity_sku, warehouse_id, snapshot_date)` 上的唯一约束（`ON CONFLICT DO NOTHING`）。该约束仅存在于迁移中，未在 ORM 模型中声明。Alembic autogenerate 会提议删除该约束 |

**修复方案**：

```python
# backend/app/models/inventory.py — InventorySnapshotHistory 类
class InventorySnapshotHistory(Base):
    __tablename__ = "inventory_snapshot_history"
    __table_args__ = (
        UniqueConstraint("commodity_sku", "warehouse_id", "snapshot_date",
                         name="uq_inv_snap_sku_wh_date"),
    )
    # ... 其他字段不变
```

---

### B-05: 回滚脚本 `git checkout` 导致 detached HEAD

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/scripts/rollback.sh` |
| 行号 | 28 |
| 严重程度 | 高 |
| 影响 | `git checkout "$PREV_SHA"` 使仓库进入 detached HEAD，后续 `git pull` 和 `deploy.sh` 将失败 |

**修复方案**：

```bash
# deploy/scripts/rollback.sh — 替换 line 28
git checkout -B "rollback-$(date +%Y%m%d-%H%M%S)" "$PREV_SHA"
```

---

### B-06: `restore_db.sh` 在已有数据上恢复，导致冲突

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/scripts/restore_db.sh` |
| 行号 | 21-22 |
| 严重程度 | 高 |
| 影响 | 直接在现有数据库上应用 SQL dump，会导致重复数据或约束冲突 |

**修复方案**：

```bash
# deploy/scripts/restore_db.sh — 在恢复之前先清理
echo "正在重建数据库..."
docker compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS replenish;"
docker compose exec -T db psql -U postgres -c "CREATE DATABASE replenish OWNER postgres;"

echo "正在恢复备份..."
gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U postgres -d replenish
```

---

## 2. 安全问题（SECURITY）

### S-01: CSP `unsafe-inline` 削弱 XSS 防护

| 属性 | 值 |
|---|---|
| 角色 | 运维 / 前端 |
| 文件 | `deploy/Caddyfile` |
| 行号 | 10 |
| 影响 | `script-src 'self' 'unsafe-inline'` 使 CSP 对 XSS 的防护大打折扣 |

**修复方案**：

短期可接受（SPA 常见权衡）。长期方案：
1. 前端构建时为内联脚本生成 nonce 或 hash
2. Caddy 通过模板注入 nonce：`script-src 'self' 'nonce-{$NONCE}'`
3. 移除所有内联 `<script>` 标签，改用外部文件

**建议优先级**：低——内部系统暂可接受，外网暴露前必须修复

---

### S-02: 健康检查端点公开暴露内部状态

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/Caddyfile` |
| 行号 | 31-37 |
| 影响 | `/healthz` 和 `/readyz` 对公网暴露数据库连通性和后台服务状态 |

**修复方案**：

```caddyfile
# deploy/Caddyfile — 限制健康检查端点访问
@health_internal {
    path /healthz /readyz
    remote_ip 127.0.0.1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
}
handle @health_internal {
    reverse_proxy backend:8000
}
# 对外返回 404
handle /healthz {
    respond 404
}
handle /readyz {
    respond 404
}
```

---

### S-03: OpenAPI 文档端点无访问控制

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/Caddyfile` |
| 行号 | 23-29 |
| 影响 | 即使 `APP_DOCS_ENABLED=true`，API 文档也对所有人可访问 |

**修复方案**：

在 Caddy 中添加 Basic Auth 或 IP 限制：
```caddyfile
handle /docs* {
    basicauth {
        admin $2a$14$... # bcrypt hash
    }
    reverse_proxy backend:8000
}
```

或直接保持 `APP_DOCS_ENABLED=false` 并在文档中强调。

---

### S-04: 前端容器以 root 运行

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `frontend/Dockerfile` |
| 影响 | Nginx 以 root 身份运行，容器逃逸攻击面更大 |

**修复方案**：

```dockerfile
# frontend/Dockerfile — 在 EXPOSE 之前添加
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d && \
    chmod -R 755 /usr/share/nginx/html
USER nginx
```

---

### S-05: X-Forwarded-For 无条件信任

| 属性 | 值 |
|---|---|
| 角色 | 后端 / 运维 |
| 文件 | `backend/app/api/auth.py:37-49`, `backend/app/core/rate_limit.py:68-77` |
| 影响 | 绕过 Caddy 直连后端时可伪造 IP，绕过速率限制和登录锁定 |

**修复方案**：

确保 Docker 网络配置中后端仅监听内部网络（当前已是如此——只有 Caddy 暴露端口）。额外防护：

```python
# backend/app/core/rate_limit.py — 添加 trusted proxy 验证
TRUSTED_PROXIES = {"172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16"}

def _get_client_ip(self, request: Request) -> str:
    # 仅当请求来自可信代理时才信任 X-Forwarded-For
    peer_ip = request.client.host if request.client else "unknown"
    if self._is_trusted_proxy(peer_ip):
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    return peer_ip
```

**建议优先级**：中——当前 Docker 网络隔离已提供保护，但应作为纵深防御添加

---

### S-06: Docker 基础镜像未固定 digest

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `backend/Dockerfile:1,19`, `frontend/Dockerfile:1,11` |
| 影响 | 供应链攻击风险——浮动标签可能被替换 |

**修复方案**：

```dockerfile
# 固定到具体 digest
FROM python:3.11-slim@sha256:<current-digest> AS builder
FROM node:20-alpine@sha256:<current-digest> AS build
FROM nginx:1.27-alpine@sha256:<current-digest>
```

通过 Dependabot 或 Renovate 自动更新 digest。

---

### S-07: 部署 SSH Action 未固定到完整 SHA

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `.github/workflows/deploy.yml:16` |
| 影响 | 第三方 Action 版本标签可被篡改 |

**修复方案**：

```yaml
# .github/workflows/deploy.yml
- uses: appleboy/ssh-action@<full-40-char-sha>
```

---

## 3. 性能问题（PERFORMANCE）

### P-01: 所有 GET 端点触发不必要的 COMMIT

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/db/session.py` |
| 行号 | 34-43 |
| 影响 | `get_db()` 依赖在成功时 auto-commit，即使只执行了 SELECT 查询也会发 COMMIT 命令，每个只读请求额外一次数据库往返 |

**修复方案**：

方案 A（推荐——最小改动）：为只读端点提供一个不 commit 的依赖：

```python
# backend/app/db/session.py
async def get_db_readonly() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()  # 只读，直接 rollback 释放
```

方案 B：将 `get_db()` 改为不自动 commit，在需要写入的端点显式 `await db.commit()`。

**影响范围**：所有 GET 端点改用 `get_db_readonly`，POST/PUT/DELETE 保持 `get_db`。

---

### P-02: 前端全量导入 Element Plus

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/main.ts:5-6` |
| 影响 | 全量导入所有 Element Plus 组件 + 完整 CSS（~300KB 未压缩），显著增大首屏包体积 |

**修复方案**：

1. 安装按需导入插件：
```bash
npm install -D unplugin-vue-components unplugin-auto-import
```

2. 配置 `vite.config.ts`：
```typescript
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
})
```

3. 移除 `main.ts` 中的全量导入：
```typescript
// 删除以下两行
// import ElementPlus from 'element-plus'
// import 'element-plus/dist/index.css'
// app.use(ElementPlus)
```

4. 保留 `element-overrides.scss` 中的自定义样式。

**预期效果**：首屏 JS 体积减少约 200-400KB（gzip 后约 60-120KB）。

---

### P-03: 登录页渲染 2800 个装饰性 DOM 元素

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/views/LoginView.vue:74` |
| 影响 | 每个 grid cell 都有 CSS transition，2800 个元素导致 DOM 压力大、首屏渲染慢 |

**修复方案**：

方案 A：减少到 400-600 个 cell（减小 grid 密度）
方案 B：改用 CSS `background` 渐变 + hover 伪元素实现类似效果
方案 C：使用 Canvas 绘制，避免 DOM 开销

推荐方案 A——最小改动：
```typescript
const GRID_CELL_COUNT = 500  // 从 2800 减少到 500
```

---

### P-04: `SuggestionDetailView` 中 `hasChanges` 使用 JSON.stringify 比较

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/views/SuggestionDetailView.vue:288` |
| 影响 | 每次渲染都对每个 item 执行 JSON 序列化比较，item 多时 UI 卡顿 |

**修复方案**：

使用 `computed` + 深度比较工具替代每次渲染的序列化：

```typescript
// 为每个 item 缓存初始状态 hash，仅在 editing state 变化时重新计算
const itemChangedMap = computed(() => {
  const map = new Map<number, boolean>()
  for (const [id, state] of editingStates.entries()) {
    const original = originalStates.get(id)
    map.set(id, !shallowEqual(state, original))
  }
  return map
})
```

或使用 `lodash.isEqual` 替代 `JSON.stringify` 比较。

---

### P-05: 同步任务在单个大事务中累积所有 UPSERT

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/sync/inventory.py:44-47`, `backend/app/sync/order_list.py:57-68` |
| 影响 | 整个同步过程（可能数千条记录）在一个事务中完成，长时间持有行锁，阻塞其他查询 |

**修复方案**：

分批 commit，每 500 条一批：

```python
# backend/app/sync/inventory.py — 示例
BATCH_SIZE = 500
count = 0
async for page in client.iter_inventory(...):
    for item in page:
        stmt = insert(Inventory).values(...).on_conflict_do_update(...)
        await db.execute(stmt)
        count += 1
        if count % BATCH_SIZE == 0:
            await db.commit()
await db.commit()  # 提交剩余
```

**注意**：需要确保部分 commit 失败时的幂等性（当前 UPSERT 已经是幂等的，所以安全）。

---

### P-06: Dashboard `build_dashboard_payload()` 作为 GET 的降级计算路径

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/api/metrics.py:461-462` |
| 影响 | 当快照缓存不存在时，GET `/api/metrics/dashboard` 会入队后台任务刷新，但如果任务执行时间长，用户会等待较久 |

**修复方案（当前逻辑已较合理）**：

确认当前实现是"返回缓存 → 无缓存则入队并返回 `refreshing` 状态"模式，前端轮询等待。若确认如此，此项无需修改，仅需确保：
1. 入队任务有去重保护（避免重复入队）
2. 前端轮询有超时退出
3. 后台任务有合理超时

---

## 4. 健壮性问题（ROBUSTNESS）

### R-01: `InTransitRecord.target_warehouse_id` FK 缺少 `ondelete` 行为

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/models/in_transit.py:35` |
| 影响 | 删除仓库时，若存在关联的在途记录，会抛出数据库外键约束错误（500） |

**修复方案**：

```python
# backend/app/models/in_transit.py
target_warehouse_id = Column(
    Integer,
    ForeignKey("warehouse.id", ondelete="SET NULL"),
    nullable=True,
)
```

需要配套 Alembic 迁移。

---

### R-02: `toggle_user_status` 两次 UPDATE 之间有竞态窗口

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/api/auth_users.py:257-262` |
| 影响 | `is_active` 和 `perm_version` 分两次 UPDATE，中间有短暂窗口用户状态不一致 |

**修复方案**：

合并为单次 UPDATE：

```python
await db.execute(
    update(SysUser)
    .where(SysUser.id == user_id)
    .values(is_active=new_status, perm_version=SysUser.perm_version + 1)
)
await db.commit()
```

---

### R-03: `inventory_snapshot_history` 表无保留策略，无限增长

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/app/tasks/jobs/daily_archive.py` |
| 影响 | 每天归档一次，历史快照无清理，数月后表会非常大 |

**修复方案**：

在 `daily_archive` 任务末尾添加清理逻辑：

```python
# backend/app/tasks/jobs/daily_archive.py — 在归档逻辑之后
RETENTION_DAYS = 90  # 保留 90 天历史
cutoff = date.today() - timedelta(days=RETENTION_DAYS)
await db.execute(
    delete(InventorySnapshotHistory)
    .where(InventorySnapshotHistory.snapshot_date < cutoff)
)
await db.commit()
logger.info("snapshot_cleanup_done", cutoff=str(cutoff))
```

---

### R-04: 无锁保护的数据库迁移

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/scripts/migrate.sh:9` |
| 影响 | 两次部署重叠时，并发迁移可能破坏数据库 schema |

**修复方案**：

```bash
# deploy/scripts/migrate.sh — 用 advisory lock 包裹迁移
docker compose exec backend python -c "
import asyncio
from sqlalchemy import text
from app.db.session import async_session_factory

async def migrate_with_lock():
    async with async_session_factory() as session:
        # 尝试获取 advisory lock，获取失败则退出
        result = await session.execute(text('SELECT pg_try_advisory_lock(99999)'))
        if not result.scalar():
            print('Another migration is running, aborting')
            exit(1)
        # lock acquired, run migration
" || exit 1
docker compose exec backend alembic upgrade head
```

或更简单——使用文件锁：
```bash
LOCK_FILE="/tmp/migrate.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Migration already running"; exit 1; }
docker compose exec backend alembic upgrade head
```

---

## 5. 错误处理缺口（ERROR HANDLING）

### E-01: 前端缺少全局错误处理器

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/main.ts` |
| 影响 | 组件生命周期中的未捕获错误静默失败，unhandled promise rejection 无任何用户反馈 |

**修复方案**：

```typescript
// frontend/src/main.ts — 在 app.mount 之前添加
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err, info)
  ElMessage.error('操作异常，请刷新页面重试')
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
})
```

---

### E-02: `GlobalConfigView` onMounted 无 try/catch

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/views/GlobalConfigView.vue:180-184` |
| 影响 | API 调用失败时，`form` 保持 `null`，页面显示空白无任何错误提示 |

**修复方案**：

```typescript
onMounted(async () => {
  try {
    const res = await getGlobalConfig()
    form.value = res.data
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载全局配置'))
  }
})
```

---

### E-03: `SyncLogView` 和 `SyncConsoleView` 多个函数缺少错误处理

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/views/SyncLogView.vue:166-174`, `frontend/src/views/SyncConsoleView.vue:230-232` |
| 影响 | `loadSyncState`、`loadOverview`、`loadRecentCalls` 均无 try/catch，API 失败时异常未处理 |

**修复方案**：

为每个加载函数包裹 try/catch：

```typescript
async function loadSyncState() {
  try {
    const res = await listSyncState()
    syncState.value = res.data
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载同步状态'))
  }
}
```

对 `loadOverview` 和 `loadRecentCalls` 同理处理。

---

### E-04: API 401 响应触发硬跳转，丢失未保存状态

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/api/client.ts:28-29` |
| 影响 | Token 过期时直接 `window.location.href = '/login'`，用户正在编辑的补货建议数据丢失 |

**修复方案（分步）**：

**短期（最小改动）**：用 Vue Router 替代硬跳转，避免丢失内存状态：
```typescript
// 在 interceptor 中
import router from '@/router'
// 替换 window.location.href = '/login'
router.replace({ path: '/login', query: { redirect: window.location.pathname } })
```

**长期**：实现 token refresh 机制（需后端配合提供 refresh token 端点）。

---

## 6. 类型安全与代码质量（CODE QUALITY）

### Q-01: `_mapUserInfo` 使用不安全的类型断言

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/stores/auth.ts:70-80` |
| 影响 | 对 `Record<string, unknown>` 直接用 `as number`、`as string` 断言，后端返回异常结构时会产生隐性 bug |

**修复方案**：

使用 Zod 或手动运行时校验：

```typescript
function _mapUserInfo(raw: Record<string, unknown>): UserInfo {
  return {
    id: Number(raw.id) || 0,
    username: String(raw.username || ''),
    displayName: String(raw.display_name || raw.username || ''),
    role: String(raw.role || ''),
    permissions: Array.isArray(raw.permissions) ? raw.permissions : [],
    isActive: Boolean(raw.is_active),
  }
}
```

---

### Q-02: `SuggestionListView` 直接使用 `client.post` 绕过类型化 API 层

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/views/SuggestionListView.vue:113,184` |
| 影响 | `/api/engine/run` 端点调用绕过了统一的 API 抽象层，缺少类型安全 |

**修复方案**：

在 API 层新增类型化函数：

```typescript
// frontend/src/api/engine.ts
export function runEngine() {
  return client.post<{ task_id: string }>('/api/engine/run')
}
```

然后在 `SuggestionListView.vue` 中使用此函数。

---

### Q-03: `AppLayout.vue` 中 `as any` 类型断言

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/src/components/AppLayout.vue:202` |
| 影响 | 绕过类型检查，可能隐藏运行时错误 |

**修复方案**：

使用类型守卫替代 `as any`：

```typescript
if ('permission' in child && child.permission) {
  // ...
}
```

---

### Q-04: Vitest 覆盖率阈值仅 2%

| 属性 | 值 |
|---|---|
| 角色 | 前端工程师 |
| 文件 | `frontend/vitest.config.ts:19` |
| 影响 | 覆盖率门槛形同虚设 |

**修复方案**：

逐步提高阈值：

```typescript
// frontend/vitest.config.ts
coverage: {
  statements: 30,  // 先设为 30%，逐步提升
  branches: 20,
  functions: 25,
  lines: 30,
}
```

---

## 7. 扩展性问题（SCALABILITY）

### SC-01: 历史记录页 `page_size=5000` 全量加载

| 属性 | 值 |
|---|---|
| 角色 | 架构师 / 前端 |
| 文件 | `frontend/src/views/HistoryView.vue:117-125` |
| 影响 | 历史记录随时间累积，5000 条限制终将不够，性能持续下降 |

**修复方案（保持现有模式的渐进方案）**：

**短期**：在 API 层添加时间范围过滤（如最近 30/60/90 天），减少单次返回量：
```typescript
const { data } = await listSuggestions({ 
  page_size: 5000, 
  days: dateRange.value  // 默认 30 天
})
```

**长期**：历史记录页改为服务端分页模式（与其他数据页不同的模式，因为历史数据量级不同）。

---

### SC-02: APScheduler 3.x 已进入维护模式

| 属性 | 值 |
|---|---|
| 角色 | 后端工程师 |
| 文件 | `backend/pyproject.toml:28` |
| 影响 | APScheduler 3.x 不再接收新功能，4.x 提供了原生异步支持 |

**修复方案**：

当前功能稳定，不建议立即迁移。记录为技术债：
- 在下一个大版本升级周期中评估 APScheduler 4.x 迁移
- 当前 3.x 的 async wrapper 运行良好

---

### SC-03: 无 Python 依赖 lockfile

| 属性 | 值 |
|---|---|
| 角色 | 后端 / 运维 |
| 文件 | `backend/pyproject.toml` |
| 影响 | 只有下界版本约束，`pip install` 可能拉取不兼容的新版本，构建不可复现 |

**修复方案**：

```bash
# 生成 lockfile
cd backend
pip install pip-tools
pip-compile pyproject.toml -o requirements.lock
```

在 Dockerfile 中使用 `requirements.lock`：
```dockerfile
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
```

---

## 8. 部署与运维优化（DEPLOYMENT）

### D-01: 无容器日志轮转

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/docker-compose.yml`（所有服务） |
| 影响 | Docker 默认 `json-file` 驱动无大小限制，日志无限增长直至磁盘满 |

**修复方案**：

在 `docker-compose.yml` 中为所有服务添加日志配置：

```yaml
# deploy/docker-compose.yml — 添加 YAML anchor
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"

services:
  db:
    logging: *default-logging
  backend:
    logging: *default-logging
  worker:
    logging: *default-logging
  scheduler:
    logging: *default-logging
  frontend:
    logging: *default-logging
  caddy:
    logging: *default-logging
```

---

### D-02: 无 CPU 限制

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/docker-compose.yml`（所有 `deploy.resources.limits`） |
| 影响 | 一个容器 CPU 失控可饿死所有其他服务 |

**修复方案**：

```yaml
services:
  db:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
  worker:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
  scheduler:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.25'
  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.25'
  caddy:
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.25'
```

---

### D-03: 无零停机部署

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/scripts/deploy.sh:50` |
| 影响 | 所有服务同时重启，部署期间完全不可用 |

**修复方案**：

采用滚动重启策略：

```bash
# deploy/scripts/deploy.sh — 替换一次性重启为滚动更新
echo ">>> 滚动更新后端服务..."
docker compose up -d --no-deps --build backend
sleep 5
docker compose exec backend curl -sf http://localhost:8000/healthz || exit 1

docker compose up -d --no-deps --build worker
sleep 5

docker compose up -d --no-deps --build scheduler
sleep 5

echo ">>> 更新前端..."
docker compose up -d --no-deps --build frontend
sleep 3

echo ">>> 重载 Caddy..."
docker compose up -d --no-deps caddy
```

---

### D-04: 无 PostgreSQL 性能调优

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/docker-compose.yml` |
| 影响 | PostgreSQL 使用 Alpine 默认配置，在 1GB 内存限制下性能不佳 |

**修复方案**：

创建自定义 PostgreSQL 配置：

```bash
# deploy/postgres/custom.conf
shared_buffers = 256MB
effective_cache_size = 512MB
work_mem = 4MB
maintenance_work_mem = 64MB
max_connections = 50
wal_buffers = 8MB
checkpoint_completion_target = 0.9
random_page_cost = 1.1
```

挂载到容器：
```yaml
# deploy/docker-compose.yml — db 服务
volumes:
  - pgdata:/var/lib/postgresql/data
  - ./postgres/custom.conf:/etc/postgresql/conf.d/custom.conf
command: postgres -c 'config_file=/etc/postgresql/conf.d/custom.conf'
```

---

### D-05: 前端服务无健康检查（compose 层）

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/docker-compose.yml:124-137,155` |
| 影响 | Caddy 依赖 `service_started` 而非 `service_healthy`，可能在 nginx 未就绪时启动 |

**修复方案**：

```yaml
# deploy/docker-compose.yml — frontend 服务
frontend:
  healthcheck:
    test: ["CMD", "wget", "-qO-", "http://localhost/"]
    interval: 10s
    timeout: 3s
    retries: 3
    start_period: 5s

# caddy 服务依赖改为
caddy:
  depends_on:
    frontend:
      condition: service_healthy
    backend:
      condition: service_healthy
```

---

### D-06: 无定时备份调度

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 影响 | 数据库备份仅在部署时触发，日常无定时备份 |

**修复方案**：

方案 A：在服务器上添加 crontab：
```bash
# crontab -e
0 3 * * * /path/to/deploy/scripts/pg_backup.sh >> /var/log/backup.log 2>&1
```

方案 B：在 `docker-compose.yml` 中添加备份服务：
```yaml
backup:
  image: postgres:16-alpine
  volumes:
    - ./scripts/pg_backup.sh:/backup.sh
    - backup_data:/backups
  entrypoint: /bin/sh -c "while true; do /backup.sh; sleep 86400; done"
  depends_on:
    db:
      condition: service_healthy
```

---

### D-07: 备份无完整性验证

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/scripts/pg_backup.sh`（line 23 之后） |
| 影响 | 空备份或损坏备份可能覆盖有效备份 |

**修复方案**：

```bash
# deploy/scripts/pg_backup.sh — 在 gzip 之后添加验证
BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
MIN_SIZE=1024  # 最小 1KB
if [ "$BACKUP_SIZE" -lt "$MIN_SIZE" ]; then
    echo "ERROR: Backup file too small ($BACKUP_SIZE bytes), likely corrupt"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# 验证备份可读
gunzip -t "$BACKUP_FILE" || {
    echo "ERROR: Backup file is corrupt"
    rm -f "$BACKUP_FILE"
    exit 1
}
echo "Backup verified: $BACKUP_SIZE bytes"
```

---

### D-08: Caddy 缺少请求大小限制和速率限制

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `deploy/Caddyfile` |
| 影响 | 大请求体可耗尽内存，无代理层速率限制 DDoS 可直达后端 |

**修复方案**：

```caddyfile
# deploy/Caddyfile — 在 route 之前添加
request_body {
    max_size 10MB
}
```

Caddy 原生不支持速率限制，可使用 `caddy-ratelimit` 插件或依赖后端已有的 60 req/min/IP 限制（对内部系统已足够）。

---

## 9. CI/CD 完善（CI/CD）

### CI-01: 部署工作流无 CI 门控

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `.github/workflows/deploy.yml:1-10` |
| 影响 | 手动触发部署时不要求 CI 通过，可能部署破损代码 |

**修复方案**：

```yaml
# .github/workflows/deploy.yml
on:
  workflow_dispatch:
    inputs:
      confirm:
        description: 'Type "deploy" to confirm'
        required: true
jobs:
  check-ci:
    runs-on: ubuntu-latest
    steps:
      - name: Verify CI passed
        uses: actions/github-script@v7
        with:
          script: |
            const checks = await github.rest.checks.listForRef({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.sha,
            });
            const ci = checks.data.check_runs.find(c => c.name === 'ci');
            if (!ci || ci.conclusion !== 'success') {
              core.setFailed('CI has not passed for this commit');
            }
  deploy:
    needs: check-ci
    # ... 现有部署步骤
```

---

### CI-02: CI 缺少 Docker 构建测试

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `.github/workflows/ci.yml` |
| 影响 | Dockerfile 问题直到部署时才发现 |

**修复方案**：

```yaml
# .github/workflows/ci.yml — 新增 job
docker-build:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Build backend image
      run: docker build -t restock-backend:test ./backend
    - name: Build frontend image
      run: docker build -t restock-frontend:test ./frontend
```

---

### CI-03: 部署缺少并发控制

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `.github/workflows/deploy.yml` |
| 影响 | 两次手动触发可能并发执行，互相干扰 |

**修复方案**：

```yaml
# .github/workflows/deploy.yml — 顶层添加
concurrency:
  group: production-deploy
  cancel-in-progress: false
```

---

### CI-04: 缺少部署通知

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 文件 | `.github/workflows/deploy.yml` |
| 影响 | 部署成功或失败无通知，需手动检查 |

**修复方案**：

部署完成后添加通知步骤（以 webhook 为例）：

```yaml
- name: Notify deploy result
  if: always()
  run: |
    STATUS="${{ job.status }}"
    curl -X POST "${{ secrets.NOTIFY_WEBHOOK }}" \
      -H "Content-Type: application/json" \
      -d "{\"text\": \"Deploy $STATUS - ${{ github.sha }}\"}"
```

---

## 10. 监控与可观测性（OBSERVABILITY）

### O-01: 缺少 Prometheus/OpenTelemetry 指标端点

| 属性 | 值 |
|---|---|
| 角色 | 运维 / 后端 |
| 影响 | 无法监控请求延迟、错误率、队列深度等关键指标 |

**修复方案（渐进式）**：

**Phase 1（最小可用）**：添加 `/metrics` 端点，暴露关键业务指标：

```python
# backend/app/api/metrics.py — 新增端点
@router.get("/api/metrics/prometheus")
async def prometheus_metrics(db: AsyncSession = Depends(get_db_readonly)):
    # 队列深度
    pending = await db.scalar(
        select(func.count()).where(TaskRun.status == "pending")
    )
    running = await db.scalar(
        select(func.count()).where(TaskRun.status == "running")
    )
    return PlainTextResponse(
        f"taskrun_pending {pending}\n"
        f"taskrun_running {running}\n"
        f"up 1\n",
        media_type="text/plain",
    )
```

**Phase 2**：集成 `prometheus-fastapi-instrumentator` 自动采集请求指标。

**Phase 3**：部署 Prometheus + Grafana（可用 Docker Compose 扩展）。

---

### O-02: 无外部健康监控

| 属性 | 值 |
|---|---|
| 角色 | 运维 |
| 影响 | 服务宕机无人知晓，完全依赖人工发现 |

**修复方案**：

注册免费的外部监控服务（如 UptimeRobot、Betterstack）：
- 监控 `/healthz` 端点
- 配置告警通知（邮件/短信/webhook）
- 检查间隔：1 分钟

---

## 11. 项目优点总结

在指出问题的同时，必须肯定项目做得好的方面：

### 架构设计
- 清晰的分层架构，依赖方向从上到下
- 进程角色分离（backend/worker/scheduler）设计精良
- 数据库即队列（TaskRun）方案简洁实用，避免引入 Redis/Celery 的运维复杂度
- `pg_advisory_xact_lock` 保护引擎并发，方案正确
- 快照机制保证建议单历史可追溯

### 后端质量
- 全链路 async/await，无阻塞
- structlog 结构化日志，request_id 自动绑定
- BusinessError 异常体系统一映射 JSON 响应
- 引擎 6 步流水线设计清晰，每步职责明确
- 推送去重保护（`dedupe_key`）防止重复推送
- Worker `FOR UPDATE SKIP LOCKED` 正确实现分布式队列模式

### 前端质量
- 一致的数据加载/错误处理/权限检查模式
- 所有路由组件懒加载，自动代码分割
- 严格 TypeScript 配置
- shadcn/ui 主题适配完整，设计系统统一
- 细粒度权限在路由守卫和 UI 元素层面双重控制
- Pinia composition API 使用规范
- `getActionErrorMessage` 统一错误消息处理

### 运维与部署
- 多阶段 Docker 构建，后端使用非 root 用户
- 完善的健康检查体系（liveness + readiness）
- YAML anchor 复用，避免配置漂移
- `.env` 文件正确 gitignore + detect-secrets 钩子
- Caddy 安全头配置全面（HSTS、CSP、Permissions-Policy）
- 部署脚本有自动回滚 trap
- Dependabot 覆盖所有生态系统

---

## 执行优先级

根据"优先功能优化、最后完善部署"原则，推荐执行顺序：

### 第一批：阻塞级 + 高优功能修复（1-2 天）

| 编号 | 任务 | 预估工作量 |
|---|---|---|
| B-01 | 添加通用 500 错误处理器 | 15 分钟 |
| B-02 | shutdown 时关闭数据库引擎 | 10 分钟 |
| B-03 | shutdown 时关闭 SaihuClient | 10 分钟 |
| B-04 | ORM 模型添加唯一约束声明 | 15 分钟 |
| E-01 | 前端全局错误处理器 | 15 分钟 |
| E-02 | GlobalConfigView 错误处理 | 10 分钟 |
| E-03 | SyncLogView/SyncConsoleView 错误处理 | 20 分钟 |
| R-02 | toggle_user_status 合并 UPDATE | 10 分钟 |
| Q-02 | engine/run API 类型化封装 | 10 分钟 |

### 第二批：性能优化（1-2 天）

| 编号 | 任务 | 预估工作量 |
|---|---|---|
| P-01 | 添加 `get_db_readonly` 依赖 | 30 分钟 |
| P-02 | Element Plus 按需导入 | 1 小时 |
| P-03 | 登录页 grid cell 减少 | 10 分钟 |
| P-04 | hasChanges 优化 | 20 分钟 |
| P-05 | 同步任务分批 commit | 30 分钟 |
| R-03 | 快照历史保留策略 | 20 分钟 |

### 第三批：安全 + 健壮性 + 代码质量（1 天）

| 编号 | 任务 | 预估工作量 |
|---|---|---|
| R-01 | InTransitRecord FK ondelete | 20 分钟（含迁移） |
| S-05 | X-Forwarded-For 信任验证 | 30 分钟 |
| Q-01 | _mapUserInfo 运行时校验 | 15 分钟 |
| Q-03 | AppLayout as any 修复 | 5 分钟 |
| Q-04 | Vitest 覆盖率阈值提升 | 5 分钟 |
| E-04 | 401 用 router.replace 替代硬跳转 | 15 分钟 |
| SC-03 | Python 依赖 lockfile | 15 分钟 |

### 第四批：部署优化（1-2 天）

| 编号 | 任务 | 预估工作量 |
|---|---|---|
| D-01 | 容器日志轮转 | 10 分钟 |
| D-02 | CPU 限制 | 10 分钟 |
| D-03 | 零停机滚动部署 | 30 分钟 |
| D-04 | PostgreSQL 调优 | 20 分钟 |
| D-05 | 前端健康检查 | 10 分钟 |
| B-05 | 回滚脚本修复 | 10 分钟 |
| B-06 | restore_db.sh 修复 | 10 分钟 |
| D-06 | 定时备份 | 20 分钟 |
| D-07 | 备份验证 | 15 分钟 |
| D-08 | Caddy 请求限制 | 10 分钟 |
| R-04 | 迁移锁 | 15 分钟 |

### 第五批：CI/CD + 安全加固 + 监控（1-2 天）

| 编号 | 任务 | 预估工作量 |
|---|---|---|
| CI-01 | 部署 CI 门控 | 20 分钟 |
| CI-02 | Docker 构建测试 | 15 分钟 |
| CI-03 | 并发控制 | 5 分钟 |
| CI-04 | 部署通知 | 15 分钟 |
| S-02 | 健康端点访问限制 | 15 分钟 |
| S-04 | 前端容器非 root | 15 分钟 |
| S-06 | 基础镜像固定 digest | 10 分钟 |
| S-07 | SSH Action 固定 SHA | 5 分钟 |
| O-01 | 基础指标端点 | 1 小时 |
| O-02 | 外部健康监控 | 30 分钟 |

### 可选 / 长期（按需）

| 编号 | 任务 | 说明 |
|---|---|---|
| SC-01 | 历史记录页服务端分页 | 数据量大时再改 |
| SC-02 | APScheduler 4.x 迁移 | 下一个大版本周期 |
| S-01 | CSP 移除 unsafe-inline | 需要前端构建配合 |
| S-03 | OpenAPI 端点 Basic Auth | 生产默认关闭，按需 |

---

## 附录：问题总览表

| ID | 类别 | 严重程度 | 批次 | 简述 |
|---|---|---|---|---|
| B-01 | 阻塞 | 高 | 1 | 缺少通用 500 处理器，泄露堆栈 |
| B-02 | 阻塞 | 高 | 1 | DB 引擎 shutdown 未 dispose |
| B-03 | 阻塞 | 中高 | 1 | SaihuClient 连接未关闭 |
| B-04 | 阻塞 | 中高 | 1 | ORM 唯一约束缺失 |
| B-05 | 阻塞 | 高 | 4 | 回滚脚本 detached HEAD |
| B-06 | 阻塞 | 高 | 4 | restore_db.sh 数据冲突 |
| S-01 | 安全 | 低 | 可选 | CSP unsafe-inline |
| S-02 | 安全 | 中 | 5 | 健康端点公开暴露 |
| S-03 | 安全 | 低 | 可选 | OpenAPI 无访问控制 |
| S-04 | 安全 | 中 | 5 | 前端容器以 root 运行 |
| S-05 | 安全 | 中 | 3 | X-Forwarded-For 无条件信任 |
| S-06 | 安全 | 中 | 5 | Docker 镜像未固定 digest |
| S-07 | 安全 | 低 | 5 | SSH Action 未固定 SHA |
| P-01 | 性能 | 中 | 2 | GET 触发不必要 COMMIT |
| P-02 | 性能 | 高 | 2 | Element Plus 全量导入 |
| P-03 | 性能 | 低 | 2 | 登录页 2800 DOM 元素 |
| P-04 | 性能 | 中 | 2 | hasChanges JSON.stringify |
| P-05 | 性能 | 中 | 2 | 同步单大事务 |
| P-06 | 性能 | 中 | — | Dashboard GET 降级计算（已缓解） |
| R-01 | 健壮 | 中 | 3 | FK 缺 ondelete |
| R-02 | 健壮 | 中 | 1 | toggle 双 UPDATE 竞态 |
| R-03 | 健壮 | 中 | 2 | 快照无保留策略 |
| R-04 | 健壮 | 中 | 4 | 迁移无并发锁 |
| E-01 | 错误处理 | 高 | 1 | 前端无全局错误处理 |
| E-02 | 错误处理 | 中 | 1 | GlobalConfigView 无 catch |
| E-03 | 错误处理 | 中 | 1 | Sync 页面无 catch |
| E-04 | 错误处理 | 中 | 3 | 401 硬跳转丢状态 |
| Q-01 | 代码质量 | 低 | 3 | _mapUserInfo 不安全断言 |
| Q-02 | 代码质量 | 低 | 1 | engine/run 绕过 API 层 |
| Q-03 | 代码质量 | 低 | 3 | as any 类型断言 |
| Q-04 | 代码质量 | 低 | 3 | 覆盖率阈值 2% |
| SC-01 | 扩展性 | 中 | 可选 | 历史页全量加载 |
| SC-02 | 扩展性 | 低 | 可选 | APScheduler 3.x |
| SC-03 | 扩展性 | 中 | 3 | 无 Python lockfile |
| D-01 | 部署 | 高 | 4 | 无日志轮转 |
| D-02 | 部署 | 中 | 4 | 无 CPU 限制 |
| D-03 | 部署 | 中 | 4 | 无零停机部署 |
| D-04 | 部署 | 中 | 4 | PG 未调优 |
| D-05 | 部署 | 低 | 4 | 前端无 compose 健康检查 |
| D-06 | 部署 | 高 | 4 | 无定时备份 |
| D-07 | 部署 | 中 | 4 | 备份无验证 |
| D-08 | 部署 | 低 | 4 | Caddy 无请求限制 |
| CI-01 | CI/CD | 高 | 5 | 部署无 CI 门控 |
| CI-02 | CI/CD | 中 | 5 | 无 Docker 构建测试 |
| CI-03 | CI/CD | 中 | 5 | 无部署并发控制 |
| CI-04 | CI/CD | 低 | 5 | 无部署通知 |
| O-01 | 监控 | 中 | 5 | 无指标端点 |
| O-02 | 监控 | 中 | 5 | 无外部监控 |
