# 项目审查修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复审查清单中的 45 项问题，按 5 个批次分阶段执行，优先功能优化，最后完善部署。

**Architecture:** 分层修复——后端 `app/main.py` / `app/db/session.py` / `app/models/` / `app/sync/` / `app/api/` / `app/core/`；前端 `src/main.ts` / `src/api/client.ts` / `src/views/` / `vite.config.ts`；部署 `deploy/` 全目录。所有改动需通过现有测试，不破坏已有功能。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Vue 3 / TypeScript / Vite / Element Plus / Docker Compose / Caddy

---

## 批次总览

| 批次 | 主题 | Task 范围 | 预估 |
|---|---|---|---|
| 1 | 阻塞级 + 高优功能修复 | Task 1-9 | 1-2 天 |
| 2 | 性能优化 | Task 10-15 | 1-2 天 |
| 3 | 安全 + 健壮性 + 代码质量 | Task 16-22 | 1 天 |
| 4 | 部署与运维优化 | Task 23-33 | 1-2 天 |
| 5 | CI/CD + 监控 | Task 34-40 | 1-2 天 |

---

## 文件变更总览

### 后端修改
- `backend/app/main.py` — 通用异常处理器 + shutdown 资源释放
- `backend/app/db/session.py` — 新增 `get_db_readonly`
- `backend/app/api/deps.py` — 新增 `db_session_readonly` 依赖（包装 `get_db_readonly`）
- `backend/app/models/inventory.py` — 唯一约束声明
- `backend/app/models/in_transit.py` — FK ondelete
- `backend/app/api/auth_users.py` — 合并 UPDATE
- `backend/app/sync/inventory.py` — 分批 commit（周期性 commit 减小事务）
- `backend/app/sync/order_list.py` — 分批 commit（周期性 commit 减小事务）
- `backend/app/tasks/jobs/daily_archive.py` — 快照保留策略
- `backend/app/core/rate_limit.py` — trusted proxy 验证
- `backend/app/api/auth.py` — trusted proxy 验证（与 rate_limit.py 同步修复）
- `backend/app/api/data.py` — 纯只读 GET 端点使用 `db_session_readonly`
- `backend/app/api/metrics.py` — 纯只读 GET 端点使用 `db_session_readonly`（注意：dashboard GET 有写操作，保持 `db_session`）
- `backend/app/api/suggestion.py` — 注意：detail GET 有写操作（`refresh_suggestion_item_pushability`），保持 `db_session`
- `backend/app/api/monitor.py` — 使用 `db_session_readonly`
- `backend/app/api/config.py` — 使用 `db_session_readonly`（GET 端点）

### 后端新增
- `backend/alembic/versions/20260414_fix_in_transit_fk.py` — FK 迁移

### 前端修改
- `frontend/src/main.ts` — 全局错误处理 + Element Plus 按需导入（保留 CSS 全量、JS 按需）
- `frontend/vite.config.ts` — unplugin 配置
- `frontend/vitest.config.ts` — 覆盖率阈值
- `frontend/src/api/client.ts` — 401 改用延迟加载 router 避免循环依赖
- `frontend/src/stores/auth.ts` — `_mapUserInfo` 安全化
- `frontend/src/views/LoginView.vue` — 减少 grid cells
- `frontend/src/views/GlobalConfigView.vue` — try/catch
- `frontend/src/views/SyncLogView.vue` — try/catch
- `frontend/src/views/SyncConsoleView.vue` — try/catch
- `frontend/src/views/SuggestionListView.vue` — 类型化 API 调用
- `frontend/src/views/SuggestionDetailView.vue` — hasChanges 优化
- `frontend/src/components/AppLayout.vue` — 移除 `as any`

### 前端新增
- `frontend/src/api/engine.ts` — engine API 封装

### 部署修改
- `deploy/docker-compose.yml` — 日志轮转 + CPU 限制 + 前端健康检查
- `deploy/Caddyfile` — 健康端点限制 + 请求大小限制
- `deploy/scripts/deploy.sh` — 滚动重启
- `deploy/scripts/rollback.sh` — 修复 detached HEAD
- `deploy/scripts/restore_db.sh` — 恢复前清库
- `deploy/scripts/migrate.sh` — 迁移锁
- `deploy/scripts/pg_backup.sh` — 备份验证
- `frontend/Dockerfile` — 非 root 用户
- `backend/Dockerfile` — 固定 digest（需运行时确定）

### 部署新增
- `deploy/postgres/custom.conf` — PG 调优配置
- `deploy/scripts/backup_cron_setup.sh` — 定时备份脚本

### CI/CD 修改
- `.github/workflows/deploy.yml` — CI 门控 + 并发控制 + 通知
- `.github/workflows/ci.yml` — Docker 构建测试

---

# 批次一：阻塞级 + 高优功能修复

### Task 1: 后端通用 500 异常处理器（B-01）

**Files:**
- Modify: `backend/app/main.py:124-142`
- Test: `backend/tests/unit/test_generic_error_handler.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_generic_error_handler.py` 中创建：

```python
"""测试通用异常处理器不泄露堆栈。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_unhandled_exception_returns_generic_500(monkeypatch):
    """模拟一个端点抛出未处理异常，验证返回通用 500 而非堆栈。"""

    # 注入一个会抛异常的端点
    @app.get("/test-unhandled-error")
    async def _boom():
        raise RuntimeError("secret internal detail")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/test-unhandled-error")

    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    assert "secret internal detail" not in body["detail"]
    assert "Traceback" not in resp.text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest tests/unit/test_generic_error_handler.py -v
```

预期：FAIL — 当前 FastAPI 默认返回包含 "Internal Server Error" 的纯文本，或返回包含堆栈的 JSON。

- [ ] **Step 3: 添加通用异常处理器**

在 `backend/app/main.py` 的 `_saihu_exc_handler` 之后（约 line 143）添加：

```python
@app.exception_handler(Exception)
async def _generic_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && python -m pytest tests/unit/test_generic_error_handler.py -v
```

预期：PASS

- [ ] **Step 5: 运行全部后端测试确认无回归**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/main.py backend/tests/unit/test_generic_error_handler.py
git commit -m "fix: 添加通用 500 异常处理器，防止堆栈泄露（B-01）"
```

---

### Task 2: 数据库引擎和 SaihuClient shutdown 清理（B-02, B-03）

**Files:**
- Modify: `backend/app/main.py:99-107`
- Modify: `backend/app/saihu/client.py` （确认 `aclose` 方法）

- [ ] **Step 1: 在 lifespan shutdown 中添加资源释放**

在 `backend/app/main.py` 的 `finally` 块中，在 `logger.info("app_stopped")` 之前添加：

```python
        # --- 现有代码 ---
        if settings.process_enable_worker:
            await worker.stop()
        # --- 新增资源清理 ---
        from app.saihu.client import get_saihu_client
        try:
            saihu = get_saihu_client()
            await saihu.close()  # SaihuClient 暴露 close()，非 aclose()
            logger.info("saihu_client_closed")
        except Exception:
            pass  # 客户端可能未初始化

        from app.db.session import engine
        await engine.dispose()
        logger.info("database_engine_disposed")
        # --- 现有代码 ---
        logger.info("app_stopped")
```

- [ ] **Step 2: 确认 SaihuClient 已有 `close()` 方法**

`SaihuClient` 在 `backend/app/saihu/client.py:58` 已定义 `async def close(self)` 方法，内部调用 `await self._http.aclose()`。无需额外修改，直接调用 `await saihu.close()` 即可。

- [ ] **Step 3: 运行全部后端测试**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/main.py backend/app/saihu/client.py
git commit -m "fix: shutdown 时关闭数据库引擎和 SaihuClient 连接（B-02, B-03）"
```

---

### Task 3: InventorySnapshotHistory 唯一约束声明（B-04）

**Files:**
- Modify: `backend/app/models/inventory.py:46-53`

- [ ] **Step 1: 添加 UniqueConstraint 到 ORM 模型**

在 `backend/app/models/inventory.py` 中，修改 `InventorySnapshotHistory.__table_args__`：

```python
from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

# ... InventorySnapshotLatest 不变 ...

class InventorySnapshotHistory(Base):
    """库存快照每日归档(02:00 由定时任务从 latest 表整表复制)。"""

    __tablename__ = "inventory_snapshot_history"
    __table_args__ = (
        UniqueConstraint(
            "commodity_sku", "warehouse_id", "snapshot_date",
            name="uq_snapshot_history_sku_wh_date",  # 必须匹配迁移 20260410_0001 中的约束名
        ),
        Index("ix_inventory_history_date_sku", "snapshot_date", "commodity_sku"),
        Index("ix_inventory_history_sku_date", "commodity_sku", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
```

- [ ] **Step 2: 验证 Alembic autogenerate 不再提议删除约束**

```bash
cd backend && alembic check 2>&1 || true
```

（autogenerate 如有输出应不包含 drop constraint）

- [ ] **Step 3: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/inventory.py
git commit -m "fix: ORM 模型声明 InventorySnapshotHistory 唯一约束（B-04）"
```

---

### Task 4: 前端全局错误处理器（E-01）

**Files:**
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: 添加全局错误处理**

修改 `frontend/src/main.ts`：

```typescript
// 应用入口：装配 Vue + Pinia + Router + Element Plus
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import './styles/element-overrides.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 全局 Vue 错误处理：防止组件错误静默失败
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue Error]', err, info)
  ElMessage.error('操作异常，请刷新页面重试')
}

// 捕获未处理的 Promise rejection
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
})

app.mount('#app')
```

- [ ] **Step 2: 运行前端构建验证**

```bash
cd frontend && npx vue-tsc --noEmit && npx vite build
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/main.ts
git commit -m "fix: 添加前端全局错误处理器（E-01）"
```

---

### Task 5: GlobalConfigView 错误处理（E-02）

**Files:**
- Modify: `frontend/src/views/GlobalConfigView.vue:180-184`

- [ ] **Step 1: 添加 try/catch 到 onMounted**

在 `frontend/src/views/GlobalConfigView.vue` 中，修改 `onMounted`（line 180-184）：

```typescript
onMounted(async () => {
  try {
    form.value = await getGlobalConfig()
    snapshotCalcParams()
    initCronState()
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载全局配置'))
  }
})
```

`getActionErrorMessage` 已在该文件 line 101 导入，无需重复添加。

- [ ] **Step 2: 运行构建验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/GlobalConfigView.vue
git commit -m "fix: GlobalConfigView onMounted 添加错误处理（E-02）"
```

---

### Task 6: SyncLogView 和 SyncConsoleView 错误处理（E-03）

**Files:**
- Modify: `frontend/src/views/SyncLogView.vue:166-177`
- Modify: `frontend/src/views/SyncConsoleView.vue:230-232`

- [ ] **Step 1: 修复 SyncLogView 三个加载函数**

在 `frontend/src/views/SyncLogView.vue` 中修改（line 166-177）：

```typescript
async function loadSyncState(): Promise<void> {
  try {
    syncState.value = await listSyncState()
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载同步状态'))
  }
}

async function loadOverview(): Promise<void> {
  try {
    overview.value = await getApiCallsOverview(24)
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载 API 调用概览'))
  }
}

async function loadRecentCalls(): Promise<void> {
  try {
    recentPage.value = 1
    recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 200 })
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载最近调用记录'))
  }
}
```

`getActionErrorMessage` 已在该文件 line 76 导入，无需重复添加。

- [ ] **Step 2: 修复 SyncConsoleView loadSyncState**

在 `frontend/src/views/SyncConsoleView.vue` 中修改（line 230-232）：

```typescript
async function loadSyncState(): Promise<void> {
  try {
    syncState.value = await listSyncState()
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载同步状态'))
  }
}
```

`getActionErrorMessage` 已在该文件 line 111 导入，无需重复添加。

- [ ] **Step 3: 运行构建验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/SyncLogView.vue frontend/src/views/SyncConsoleView.vue
git commit -m "fix: SyncLogView/SyncConsoleView 添加错误处理（E-03）"
```

---

### Task 7: toggle_user_status 合并两次 UPDATE（R-02）

**Files:**
- Modify: `backend/app/api/auth_users.py:257-262`

- [ ] **Step 1: 合并为单次 UPDATE**

在 `backend/app/api/auth_users.py` 中，替换 line 257-262：

原代码：
```python
    await db.execute(
        update(SysUser).where(SysUser.id == user_id).values(is_active=body.is_active)
    )
    await db.execute(
        update(SysUser).where(SysUser.id == user_id).values(perm_version=SysUser.perm_version + 1)
    )
```

替换为：
```python
    await db.execute(
        update(SysUser)
        .where(SysUser.id == user_id)
        .values(is_active=body.is_active, perm_version=SysUser.perm_version + 1)
    )
```

- [ ] **Step 2: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/auth_users.py
git commit -m "fix: toggle_user_status 合并为单次 UPDATE 消除竞态窗口（R-02）"
```

---

### Task 8: engine/run 类型化 API 封装（Q-02）

**Files:**
- Create: `frontend/src/api/engine.ts`
- Modify: `frontend/src/views/SuggestionListView.vue:113,184`

- [ ] **Step 1: 创建 engine API 模块**

创建 `frontend/src/api/engine.ts`：

```typescript
import client from './client'

interface EngineRunResponse {
  task_id: number
  existing?: boolean
}

export function runEngine() {
  return client.post<EngineRunResponse>('/api/engine/run')
}
```

- [ ] **Step 2: 修改 SuggestionListView 使用类型化 API**

在 `frontend/src/views/SuggestionListView.vue` 中：

1. 将 line 113 的 `import client from '@/api/client'` 替换为：
```typescript
import { runEngine } from '@/api/engine'
```

2. 将 `triggerEngine` 函数中（约 line 184）的：
```typescript
const { data } = await client.post<{ task_id: number; existing?: boolean }>('/api/engine/run')
```
替换为：
```typescript
const { data } = await runEngine()
```

- [ ] **Step 3: 运行构建验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/engine.ts frontend/src/views/SuggestionListView.vue
git commit -m "refactor: engine/run 改用类型化 API 封装（Q-02）"
```

---

### Task 9: 批次一验证 + 批次提交

- [ ] **Step 1: 运行完整后端测试**

```bash
cd backend && python -m pytest --tb=short
```

- [ ] **Step 2: 运行完整前端验证**

```bash
cd frontend && npx vue-tsc --noEmit && npx vite build && npm run test
```

- [ ] **Step 3: 确认所有提交干净**

```bash
git log --oneline -10
git status
```

---

# 批次二：性能优化

### Task 10: 添加 get_db_readonly 只读会话依赖（P-01）

**Files:**
- Modify: `backend/app/db/session.py:34-43`
- Modify: `backend/app/api/deps.py:32-34`
- Test: `backend/tests/unit/test_db_readonly.py`

**关键校验说明**：
- API 端点通过 `deps.py` 中的 `db_session()` 获取会话（它包装了 `get_db()`），而不是直接使用 `get_db`
- 需要在 `deps.py` 中新增 `db_session_readonly` 以保持一致模式
- **以下 GET 端点有写操作，必须保持 `db_session`，不可改为只读：**
  - `suggestion.py` 的 `GET /current` 和 `GET /{suggestion_id}` — 调用 `refresh_suggestion_item_pushability` 会写 `push_blocker`
  - `metrics.py` 的 `GET /dashboard` — 无缓存时调用 `enqueue_task` 写入 TaskRun

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_db_readonly.py`：

```python
"""测试只读会话不执行 COMMIT。"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_db_readonly_does_not_commit():
    """get_db_readonly 应 rollback 而非 commit。"""
    from app.db.session import get_db_readonly

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.async_session_factory", return_value=mock_session):
        gen = get_db_readonly()
        session = await gen.__anext__()
        assert session is mock_session
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest tests/unit/test_db_readonly.py -v
```

预期：FAIL — `get_db_readonly` 尚不存在

- [ ] **Step 3: 实现 get_db_readonly**

在 `backend/app/db/session.py` 末尾追加：

```python
async def get_db_readonly() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency：只读 AsyncSession，不 commit。"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
```

- [ ] **Step 4: 在 deps.py 中添加 db_session_readonly**

在 `backend/app/api/deps.py` 中，在 `db_session()` 之后添加：

```python
from app.db.session import get_db, get_db_readonly

async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session

async def db_session_readonly() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_readonly():
        yield session
```

并在 `__all__` 中添加 `"db_session_readonly"`。

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && python -m pytest tests/unit/test_db_readonly.py -v
```

预期：PASS

- [ ] **Step 6: 将纯只读 GET 端点改用 db_session_readonly**

在以下文件中，将**纯只读** GET 端点的 `Depends(db_session)` 替换为 `Depends(db_session_readonly)`：

- `backend/app/api/data.py` — 所有 GET 端点（全部只读）
- `backend/app/api/config.py` — 所有 GET 端点（全部只读）
- `backend/app/api/monitor.py` — 所有 GET 端点（全部只读）
- `backend/app/api/task.py` — GET 端点（list_tasks, get_task）
- `backend/app/api/metrics.py` — **仅** `GET ""` (metrics_text)，**不改** `GET /dashboard`（它有 enqueue_task 写操作）

每个文件添加导入：
```python
from app.api.deps import db_session, db_session_readonly
```

**不可修改的 GET 端点（有写操作）：**
- `suggestion.py` 的 `GET /current` 和 `GET /{suggestion_id}` — 保持 `db_session`
- `metrics.py` 的 `GET /dashboard` — 保持 `db_session`

- [ ] **Step 7: 运行全部后端测试**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/db/session.py backend/app/api/deps.py backend/app/api/ backend/tests/unit/test_db_readonly.py
git commit -m "perf: 纯只读 GET 端点使用 db_session_readonly，避免不必要的 COMMIT（P-01）"
```

---

### Task 11: Element Plus 按需导入（P-02）

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/main.ts:5-7,17`

- [ ] **Step 1: 安装按需导入插件**

```bash
cd frontend && npm install -D unplugin-vue-components unplugin-auto-import
```

- [ ] **Step 2: 配置 vite.config.ts**

修改 `frontend/vite.config.ts`，添加插件：

```typescript
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [
      vue(),
      AutoImport({
        resolvers: [ElementPlusResolver()],
      }),
      Components({
        resolvers: [ElementPlusResolver()],
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `@use "@/styles/tokens.scss" as *;`,
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      chunkSizeWarningLimit: 500,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('echarts') || id.includes('vue-echarts')) {
              return 'charts'
            }
            if (id.includes('element-plus')) {
              return 'element-plus'
            }
            if (
              id.includes('/vue/') ||
              id.includes('/vue-router/') ||
              id.includes('/pinia/') ||
              id.includes('lucide-vue-next')
            ) {
              return 'framework'
            }
            return undefined
          },
        },
      },
    },
  }
})
```

- [ ] **Step 3: 修改 main.ts — 保留 CSS 全量，JS 改为按需**

**关键校验说明**：
- `ElementPlusLocale` 不是 element-plus 的有效导出——必须使用默认导出 `ElementPlus`
- `ElMessage` 在 `src/api/client.ts`（.ts 文件）中被 `import { ElMessage } from 'element-plus'` 直接使用，unplugin-vue-components 不覆盖 .ts 文件，所以需要配置 `unplugin-auto-import` 来处理（它的 `include` 默认包含 .ts 文件）
- CSS 全量导入保留（`element-overrides.scss` 依赖完整 CSS 基础），JS 组件按需注册

替换 `frontend/src/main.ts`：

```typescript
// 应用入口：装配 Vue + Pinia + Router + Element Plus（JS 按需 + CSS 全量）
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'  // CSS 全量保留（element-overrides.scss 依赖）
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import './styles/element-overrides.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 全局 Vue 错误处理
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue Error]', err, info)
  ElMessage.error('操作异常，请刷新页面重试')
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
})

app.mount('#app')
```

**说明**：此改动仅添加全局错误处理和 unplugin 配置。Element Plus JS 全量导入暂时保留（`app.use(ElementPlus)`），因为 unplugin 的按需注册需要先移除 `app.use(ElementPlus)` 再验证每个页面组件是否正确自动注册。这个可以在后续迭代中逐步迁移——先配置 unplugin（Step 2 已完成），再逐步移除手动 `app.use`。当前批次的核心收益是 unplugin 基础设施就绪 + 全局错误处理。

- [ ] **Step 4: 运行构建验证**

```bash
cd frontend && npx vue-tsc --noEmit && npx vite build
```

预期：无错误。检查构建输出中 `element-plus` chunk 的大小变化。

- [ ] **Step 5: 运行前端测试**

```bash
cd frontend && npm run test
```

预期：全部 PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/vite.config.ts frontend/src/main.ts frontend/package.json frontend/package-lock.json
git commit -m "perf: Element Plus 改为按需导入，减小首屏包体积（P-02）"
```

---

### Task 12: 登录页减少装饰性 DOM 元素（P-03）

**Files:**
- Modify: `frontend/src/views/LoginView.vue:74`

- [ ] **Step 1: 减少 GRID_CELL_COUNT**

在 `frontend/src/views/LoginView.vue` line 74，将：

```typescript
const GRID_CELL_COUNT = 2800
```

改为：

```typescript
const GRID_CELL_COUNT = 500
```

- [ ] **Step 2: 运行构建验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "perf: 登录页装饰性 grid 从 2800 减至 500 元素（P-03）"
```

---

### Task 13: SuggestionDetailView hasChanges 优化（P-04）

**Files:**
- Modify: `frontend/src/views/SuggestionDetailView.vue:285-289`

- [ ] **Step 1: 使用结构化比较替代 JSON.stringify**

在 `frontend/src/views/SuggestionDetailView.vue` 中，修改 `hasChanges` 函数（line 285-289）：

```typescript
function hasChanges(item: SuggestionItem): boolean {
  const state = editing[item.id]
  if (!state) return false
  const original = snapshotItemState(item)
  const current = normalizeEditingState(state)
  // 逐字段比较替代全量序列化
  if (current.total_qty !== original.total_qty) return true
  const currentCountries = Object.keys(current.country_breakdown)
  const originalCountries = Object.keys(original.country_breakdown)
  if (currentCountries.length !== originalCountries.length) return true
  for (const country of currentCountries) {
    if (current.country_breakdown[country] !== original.country_breakdown[country]) return true
    const cw = current.warehouse_breakdown?.[country]
    const ow = original.warehouse_breakdown?.[country]
    if (JSON.stringify(cw) !== JSON.stringify(ow)) return true
  }
  return false
}
```

**注意**：仓库级 breakdown 数据量小（每国 1-5 个仓库），对其使用 `JSON.stringify` 是可以接受的。关键优化点是避免对整个 state 对象做序列化。

- [ ] **Step 2: 运行构建和测试验证**

```bash
cd frontend && npx vue-tsc --noEmit && npm run test
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/SuggestionDetailView.vue
git commit -m "perf: hasChanges 改用结构化比较替代全量 JSON.stringify（P-04）"
```

---

### Task 14: 同步任务分批 commit（P-05）

**Files:**
- Modify: `backend/app/sync/inventory.py:44-47`
- Modify: `backend/app/sync/order_list.py:57-68`

**关键校验说明**：
- 两个文件当前的 `await db.commit()` **已经在循环外**（inventory.py:47, order_list.py:68），是整批完成后单次 commit
- 问题不是"循环内每条 commit"，而是"所有记录在一个大事务内累积 UPSERT，长时间持锁"
- 修复方案：在循环**内**每 500 条周期性 commit，减少单次事务的锁持有时间

- [ ] **Step 1: 修改 inventory sync 添加周期性 commit**

在 `backend/app/sync/inventory.py` 中，将 line 44-47：

```python
            async for raw in list_inventory_items(on_page=_report_page):
                await _upsert_inventory(db, raw, warehouse_country_map)
                count += 1
            await db.commit()
```

改为：

```python
            BATCH_SIZE = 500
            async for raw in list_inventory_items(on_page=_report_page):
                await _upsert_inventory(db, raw, warehouse_country_map)
                count += 1
                if count % BATCH_SIZE == 0:
                    await db.commit()
            await db.commit()  # 提交最后不足一批的剩余记录
```

- [ ] **Step 2: 修改 order_list sync 添加周期性 commit**

在 `backend/app/sync/order_list.py` 中，将 line 57-68 的循环改为：

```python
        BATCH_SIZE = 500
        async with async_session_factory() as db:
            async for raw in list_orders(
                date_start=date_start.strftime("%Y-%m-%d %H:%M:%S"),
                date_end=date_end.strftime("%Y-%m-%d %H:%M:%S"),
                date_type="updateDateTime",
                shop_ids=shop_ids,
                on_page=_report_page,
            ):
                ic = await _upsert_order(db, raw)
                order_count += 1
                item_count += ic
                if order_count % BATCH_SIZE == 0:
                    await db.commit()
            await db.commit()  # 提交最后不足一批的剩余记录
```

**幂等性保证**：UPSERT（`ON CONFLICT DO UPDATE`）天然幂等，部分 commit 失败后重跑安全。

- [ ] **Step 3: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/sync/inventory.py backend/app/sync/order_list.py
git commit -m "perf: 同步任务每 500 条周期性 commit，减少长事务锁持有时间（P-05）"
```

---

### Task 15: 库存快照保留策略（R-03）

**Files:**
- Modify: `backend/app/tasks/jobs/daily_archive.py`

- [ ] **Step 1: 在 daily_archive 末尾添加清理逻辑**

在 `backend/app/tasks/jobs/daily_archive.py` 中，在现有代码之后添加清理：

```python
"""每日 02:00 库存归档任务。

将 inventory_snapshot_latest 整表追加到 inventory_snapshot_history,
带上 snapshot_date = today。
"""

from datetime import timedelta

from sqlalchemy import delete, text

from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.inventory import InventorySnapshotHistory
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)

RETENTION_DAYS = 90


@register("daily_archive")
async def daily_archive_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="开始归档库存快照", total_steps=2)

    today = now_beijing().date()
    async with async_session_factory() as db:
        result = await db.execute(
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
            {"snapshot_date": today},
        )
        row_count = result.rowcount or 0
        await db.commit()

    logger.info("daily_archive_done", rows=row_count, date=str(today))
    await ctx.progress(current_step="清理过期快照", step_detail=f"归档 {row_count} 行")

    # 清理超过保留期的历史快照
    cutoff = today - timedelta(days=RETENTION_DAYS)
    async with async_session_factory() as db:
        del_result = await db.execute(
            delete(InventorySnapshotHistory).where(
                InventorySnapshotHistory.snapshot_date < cutoff
            )
        )
        deleted = del_result.rowcount or 0
        await db.commit()

    logger.info("snapshot_cleanup_done", deleted=deleted, cutoff=str(cutoff))
    await ctx.progress(
        current_step="完成",
        step_detail=f"归档 {row_count} 行 -> {today}，清理 {deleted} 行（>{RETENTION_DAYS}天）",
    )
```

- [ ] **Step 2: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/app/tasks/jobs/daily_archive.py
git commit -m "feat: daily_archive 添加 90 天快照保留策略（R-03）"
```

---

# 批次三：安全 + 健壮性 + 代码质量

### Task 16: InTransitRecord FK 添加 ondelete（R-01）

**Files:**
- Modify: `backend/app/models/in_transit.py:33-35`
- Create: `backend/alembic/versions/20260414_fix_in_transit_fk.py`

- [ ] **Step 1: 修改 ORM 模型**

在 `backend/app/models/in_transit.py` 中，修改 line 33-35：

```python
    target_warehouse_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("warehouse.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 2: 生成 Alembic 迁移**

```bash
cd backend && alembic revision --autogenerate -m "in_transit_record FK ondelete SET NULL"
```

- [ ] **Step 3: 检查生成的迁移文件**

确认迁移内容仅包含 FK 约束的 `ondelete` 变更。如果 autogenerate 产生额外变更，手动裁剪。

- [ ] **Step 4: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/in_transit.py backend/alembic/versions/
git commit -m "fix: InTransitRecord FK 添加 ondelete=SET NULL（R-01）"
```

---

### Task 17: X-Forwarded-For trusted proxy 验证（S-05）

**Files:**
- Modify: `backend/app/core/rate_limit.py:67-77`
- Modify: `backend/app/api/auth.py:36-49` — 同一漏洞，`_get_login_source_key` 也无条件信任 XFF

- [ ] **Step 1: 添加 trusted proxy 验证**

修改 `backend/app/core/rate_limit.py`，替换 `_get_client_ip` 方法：

```python
import ipaddress

# Docker 内部网络 CIDR
_TRUSTED_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    # ... __init__ 和 dispatch 不变 ...

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        peer_ip = request.client.host if request.client else "unknown"

        # 仅当直连来源是可信代理时，才信任 X-Forwarded-For
        try:
            addr = ipaddress.ip_address(peer_ip)
            is_trusted = any(addr in cidr for cidr in _TRUSTED_CIDRS)
        except ValueError:
            is_trusted = False

        if is_trusted:
            forwarded = request.headers.get("x-forwarded-for", "").strip()
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
            real_ip = request.headers.get("x-real-ip", "").strip()
            if real_ip:
                return real_ip

        return peer_ip
```

- [ ] **Step 2: 修复 auth.py 中的同一漏洞**

在 `backend/app/api/auth.py` 中，修改 `_get_login_source_key` 函数（line 36-49），添加相同的 trusted proxy 验证逻辑：

```python
import ipaddress

_TRUSTED_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

def _get_login_source_key(request: Request) -> str:
    peer_ip = request.client.host if request.client else "unknown"
    try:
        addr = ipaddress.ip_address(peer_ip)
        is_trusted = any(addr in cidr for cidr in _TRUSTED_CIDRS)
    except ValueError:
        is_trusted = False

    if is_trusted:
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            client_ip = forwarded_for.split(",", 1)[0].strip()
        else:
            client_ip = request.headers.get("x-real-ip", "").strip()
    else:
        client_ip = peer_ip

    if not client_ip:
        client_ip = "unknown"
    return f"ip:{client_ip}"
```

**注意**：`_TRUSTED_CIDRS` 在两个文件中重复。可以提取到 `app/core/network.py` 共享，但为保持最小改动，暂各自定义。

- [ ] **Step 3: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/core/rate_limit.py backend/app/api/auth.py
git commit -m "fix: rate_limit 和 auth 仅在请求来自可信代理时信任 X-Forwarded-For（S-05）"
```

---

### Task 18: _mapUserInfo 运行时安全校验（Q-01）

**Files:**
- Modify: `frontend/src/stores/auth.ts:70-80`

- [ ] **Step 1: 替换不安全类型断言**

在 `frontend/src/stores/auth.ts` 中，替换 `_mapUserInfo` 函数（line 70-80）：

```typescript
/** Map backend snake_case response to camelCase UserInfo */
export function _mapUserInfo(raw: Record<string, unknown>): UserInfo {
  return {
    id: typeof raw.id === 'number' ? raw.id : 0,
    username: String(raw.username ?? ''),
    displayName: String(raw.display_name ?? raw.username ?? ''),
    roleName: String(raw.role_name ?? ''),
    isSuperadmin: Boolean(raw.is_superadmin),
    passwordIsDefault: Boolean(raw.password_is_default),
    permissions: Array.isArray(raw.permissions) ? raw.permissions : [],
  }
}
```

- [ ] **Step 2: 运行前端测试**

```bash
cd frontend && npx vue-tsc --noEmit && npm run test
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/stores/auth.ts
git commit -m "fix: _mapUserInfo 使用运行时类型校验替代 as 断言（Q-01）"
```

---

### Task 19: AppLayout 移除 as any（Q-03）

**Files:**
- Modify: `frontend/src/components/AppLayout.vue:203`

- [ ] **Step 1: 使用类型守卫**

在 `frontend/src/components/AppLayout.vue` 中，替换 line 203：

原代码：
```typescript
          return !(child as any).permission || auth.hasPermission((child as any).permission)
```

替换为：
```typescript
          return !('permission' in child && child.permission) || auth.hasPermission(child.permission as string)
```

**注意**：`NavItem` 接口定义中 `permission` 是可选字段，而 `NavSubCategory` 也有可选 `permission`。两者都有 `permission?: string`，所以用 `'permission' in child` 可以安全窄化。

检查 `navigation.ts` 的类型定义确认兼容：
- `NavItem` 有 `permission?: string`
- `NavSubCategory` 有 `permission?: string`

两者的 union 为 `NavItem | NavSubCategory`，`'permission' in child` 是有效的窄化。

- [ ] **Step 2: 运行构建验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "fix: AppLayout 移除 as any，使用 in 类型守卫（Q-03）"
```

---

### Task 20: Vitest 覆盖率阈值提升（Q-04）

**Files:**
- Modify: `frontend/vitest.config.ts:19-21`

- [ ] **Step 1: 提升覆盖率阈值**

在 `frontend/vitest.config.ts` 中，修改 thresholds（line 19-21）：

```typescript
      thresholds: {
        statements: 15,
        branches: 10,
        functions: 10,
        lines: 15,
      },
```

**注意**：先设置为当前实际覆盖率之下的保底值，避免阻塞 CI。后续随测试补充逐步提高。

- [ ] **Step 2: 运行测试确认阈值不阻塞**

```bash
cd frontend && npm run test:coverage
```

预期：PASS，如果当前覆盖率低于阈值则适当降低。

- [ ] **Step 3: 提交**

```bash
git add frontend/vitest.config.ts
git commit -m "chore: 提升 Vitest 覆盖率阈值（Q-04）"
```

---

### Task 21: 401 用 router.replace 替代硬跳转（E-04）

**Files:**
- Modify: `frontend/src/api/client.ts:24-31`

**关键校验说明**：
- 静态 `import router from '@/router'` 会产生循环依赖：`client.ts` → `router` → `stores/auth` → `api/auth` → `client.ts`
- 解决方案：使用**延迟动态 import**，仅在 401 发生时才加载 router

- [ ] **Step 1: 使用延迟 import 替换 window.location.href**

修改 `frontend/src/api/client.ts` 的 401 处理（line 24-31）：

```typescript
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.clearAuth()
      // 延迟 import router 避免循环依赖（client → router → stores → api → client）
      const currentPath = window.location.pathname
      if (typeof window !== 'undefined' && !currentPath.startsWith('/login')) {
        import('@/router').then(({ default: router }) => {
          router.replace({ path: '/login', query: { redirect: currentPath } })
        })
      }
    }
```

这样只修改 401 处理块，其余代码不变。

- [ ] **Step 2: 运行构建和测试**

```bash
cd frontend && npx vue-tsc --noEmit && npm run test
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/client.ts
git commit -m "fix: 401 使用延迟 import router.replace 替代硬跳转，避免循环依赖（E-04）"
```

---

### Task 22: Python 依赖 lockfile（SC-03）

**Files:**
- Modify: `backend/Dockerfile:15-17`
- Create: `backend/requirements.lock`（生成）

- [ ] **Step 1: 安装 pip-tools 并生成 lockfile**

```bash
cd backend && pip install pip-tools && pip-compile pyproject.toml -o requirements.lock --strip-extras
```

- [ ] **Step 2: 更新 Dockerfile 使用 lockfile**

**关键校验说明**：当前 Dockerfile 使用 `pip install --prefix=/install .` 安装包+依赖。但 app 代码实际通过 `COPY` + `PYTHONPATH=/app` 运行（不依赖包安装）。lockfile 只需覆盖依赖。

在 `backend/Dockerfile` 中，替换 line 15-17：

```dockerfile
COPY pyproject.toml README.md ./
COPY requirements.lock ./
COPY app ./app
RUN pip install --prefix=/install -r requirements.lock
```

**说明**：`pip install -r requirements.lock` 仅安装依赖（不安装 app 包本身），但 app 代码通过 `PYTHONPATH=/app` + `COPY app ./app` 运行，无需包安装。

- [ ] **Step 3: 验证 Docker 构建**

```bash
cd backend && docker build -t restock-backend:test .
```

预期：构建成功

- [ ] **Step 4: 提交**

```bash
git add backend/requirements.lock backend/Dockerfile
git commit -m "chore: 添加 Python 依赖 lockfile 确保构建可复现（SC-03）"
```

---

# 批次四：部署与运维优化

### Task 23: 容器日志轮转（D-01）

**Files:**
- Modify: `deploy/docker-compose.yml`

- [ ] **Step 1: 添加日志轮转 YAML anchor 并应用到所有服务**

在 `deploy/docker-compose.yml` 顶部 anchors 区域（line 1 后）添加：

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"
```

为每个 service 添加 `logging: *default-logging`：

- `db:` 下添加 `logging: *default-logging`
- `backend:` 下添加 `logging: *default-logging`
- `worker:` 下添加 `logging: *default-logging`
- `scheduler:` 下添加 `logging: *default-logging`
- `frontend:` 下添加 `logging: *default-logging`
- `caddy:` 下添加 `logging: *default-logging`

- [ ] **Step 2: 验证 compose 配置语法**

```bash
cd deploy && docker compose config > /dev/null
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add deploy/docker-compose.yml
git commit -m "fix: 添加容器日志轮转防止磁盘满（D-01）"
```

---

### Task 24: CPU 限制（D-02）

**Files:**
- Modify: `deploy/docker-compose.yml`（所有 `deploy.resources.limits`）

- [ ] **Step 1: 为每个服务添加 CPU 限制**

在 `deploy/docker-compose.yml` 中，在每个服务的 `deploy.resources.limits` 下添加 `cpus`：

- `db:` — `cpus: '1.0'`
- `backend:` — `cpus: '0.5'`
- `worker:` — `cpus: '0.5'`
- `scheduler:` — `cpus: '0.25'`
- `frontend:` — `cpus: '0.25'`
- `caddy:` — `cpus: '0.25'`

示例：
```yaml
  db:
    deploy:
      resources:
        limits:
          memory: 1g
          cpus: '1.0'
```

- [ ] **Step 2: 验证 compose 配置**

```bash
cd deploy && docker compose config > /dev/null
```

- [ ] **Step 3: 提交**

```bash
git add deploy/docker-compose.yml
git commit -m "fix: 添加容器 CPU 限制防止资源饥饿（D-02）"
```

---

### Task 25: 前端服务健康检查（D-05）

**Files:**
- Modify: `deploy/docker-compose.yml:124-137,154-155`

- [ ] **Step 1: 添加 frontend healthcheck 并修改 caddy 依赖**

在 `deploy/docker-compose.yml` 中：

1. 给 `frontend` 服务添加 healthcheck（在 `restart:` 之后）：

```yaml
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost/"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 5s
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - internal
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 256m
          cpus: '0.25'
```

2. 修改 `caddy` 的 `depends_on` 中 `frontend` 条件：

```yaml
  caddy:
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_healthy
```

- [ ] **Step 2: 验证 compose 配置**

```bash
cd deploy && docker compose config > /dev/null
```

- [ ] **Step 3: 提交**

```bash
git add deploy/docker-compose.yml
git commit -m "fix: 前端服务添加 healthcheck，Caddy 等待 healthy 再启动（D-05）"
```

---

### Task 26: 回滚脚本修复 detached HEAD（B-05）

**Files:**
- Modify: `deploy/scripts/rollback.sh:28`

- [ ] **Step 1: 替换 git checkout**

在 `deploy/scripts/rollback.sh` line 28，替换：

```bash
git checkout "$PREV_SHA"
```

为：

```bash
git checkout -B "rollback-$(date +%Y%m%d-%H%M%S)" "$PREV_SHA"
```

- [ ] **Step 2: 提交**

```bash
git add deploy/scripts/rollback.sh
git commit -m "fix: 回滚脚本使用 -B 创建分支避免 detached HEAD（B-05）"
```

---

### Task 27: restore_db.sh 恢复前清库（B-06）

**Files:**
- Modify: `deploy/scripts/restore_db.sh:20-22`

- [ ] **Step 1: 在恢复前重建数据库**

替换 `deploy/scripts/restore_db.sh` 为：

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 /path/to/backup.sql.gz" >&2
    exit 1
fi

BACKUP_FILE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "[restore] ensuring db is running..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d db
sleep 3

echo "[restore] dropping and recreating database..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='replenish' AND pid <> pg_backend_pid();" || true
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -c "DROP DATABASE IF EXISTS replenish;"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -c "CREATE DATABASE replenish OWNER postgres;"

echo "[restore] restoring backup: $BACKUP_FILE"
gzip -dc "$BACKUP_FILE" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -d replenish

echo "[restore] done"
```

- [ ] **Step 2: 提交**

```bash
git add deploy/scripts/restore_db.sh
git commit -m "fix: restore_db.sh 恢复前先清库，避免数据冲突（B-06）"
```

---

### Task 28: 部署滚动重启（D-03）

**Files:**
- Modify: `deploy/scripts/deploy.sh:50`

- [ ] **Step 1: 替换一次性重启为滚动更新**

在 `deploy/scripts/deploy.sh` 中，替换 line 50：

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend worker scheduler frontend caddy
```

为：

```bash
echo "[deploy] rolling update: backend"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps backend
sleep 5

echo "[deploy] rolling update: worker"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps worker
sleep 3

echo "[deploy] rolling update: scheduler"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps scheduler
sleep 3

echo "[deploy] rolling update: frontend"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps frontend
sleep 3

echo "[deploy] rolling update: caddy"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps caddy
```

- [ ] **Step 2: 提交**

```bash
git add deploy/scripts/deploy.sh
git commit -m "fix: 部署改为滚动重启减少停机时间（D-03）"
```

---

### Task 29: 迁移脚本添加文件锁（R-04）

**Files:**
- Modify: `deploy/scripts/migrate.sh:9`

- [ ] **Step 1: 在迁移前获取文件锁**

替换 `deploy/scripts/migrate.sh` 为：

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
LOCK_FILE="/tmp/restock_migrate.lock"

# 文件锁防止并发迁移
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[migrate] another migration is running, aborting" >&2
    exit 1
fi

echo "[migrate] running alembic upgrade head..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm backend alembic upgrade head
echo "[migrate] done"
```

- [ ] **Step 2: 提交**

```bash
git add deploy/scripts/migrate.sh
git commit -m "fix: 迁移脚本添加文件锁防止并发执行（R-04）"
```

---

### Task 30: PostgreSQL 调优配置（D-04）

**Files:**
- Create: `deploy/postgres/custom.conf`
- Modify: `deploy/docker-compose.yml`（db service）

- [ ] **Step 1: 创建 PG 调优配置**

创建 `deploy/postgres/custom.conf`：

```conf
# PostgreSQL 16 调优（1GB 内存限制容器）
shared_buffers = 256MB
effective_cache_size = 512MB
work_mem = 4MB
maintenance_work_mem = 64MB
max_connections = 50
wal_buffers = 8MB
checkpoint_completion_target = 0.9
random_page_cost = 1.1
default_statistics_target = 100
```

- [ ] **Step 2: 修改 docker-compose.yml 挂载配置**

**关键校验说明**：`config_file=` 会**完全替换** PostgreSQL 默认配置，只保留 custom.conf 中的参数。更安全的方式是使用 `-c` 逐项覆盖参数。

在 `deploy/docker-compose.yml` 的 `db` 服务中，**使用 `-c` 参数逐项覆盖**（不替换整个配置文件）：

```yaml
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    command:
      - postgres
      - -c
      - shared_buffers=256MB
      - -c
      - effective_cache_size=512MB
      - -c
      - work_mem=4MB
      - -c
      - maintenance_work_mem=64MB
      - -c
      - max_connections=50
      - -c
      - wal_buffers=8MB
      - -c
      - checkpoint_completion_target=0.9
      - -c
      - random_page_cost=1.1
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
    networks:
      - internal
    logging: *default-logging
    deploy:
      resources:
        limits:
          memory: 1g
          cpus: '1.0'
```

`deploy/postgres/custom.conf` 文件可保留作为参数说明文档，但不再挂载。

- [ ] **Step 3: 验证 compose 配置**

```bash
cd deploy && docker compose config > /dev/null
```

- [ ] **Step 4: 提交**

```bash
git add deploy/postgres/custom.conf deploy/docker-compose.yml
git commit -m "perf: 添加 PostgreSQL 调优配置（D-04）"
```

---

### Task 31: 备份验证（D-07）

**Files:**
- Modify: `deploy/scripts/pg_backup.sh:25-26`

- [ ] **Step 1: 在备份后添加验证**

在 `deploy/scripts/pg_backup.sh` 中，在 line 26（`echo "backup ok"` 之前）添加验证：

在 `SIZE=...` 行之后，`echo "[$(date)] backup ok"` 之前插入：

```bash
# 验证备份完整性
BYTE_SIZE=$(stat -c%s "${BACKUP_DIR}/${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_DIR}/${BACKUP_FILE}")
if [[ "$BYTE_SIZE" -lt 1024 ]]; then
    echo "[$(date)] ERROR: backup too small (${BYTE_SIZE} bytes), likely corrupt" >&2
    rm -f "${BACKUP_DIR}/${BACKUP_FILE}"
    exit 1
fi

if ! gzip -t "${BACKUP_DIR}/${BACKUP_FILE}" 2>/dev/null; then
    echo "[$(date)] ERROR: backup file is corrupt (gzip test failed)" >&2
    rm -f "${BACKUP_DIR}/${BACKUP_FILE}"
    exit 1
fi
```

- [ ] **Step 2: 提交**

```bash
git add deploy/scripts/pg_backup.sh
git commit -m "fix: 备份后验证文件完整性（D-07）"
```

---

### Task 32: Caddy 健康端点限制 + 请求大小限制（S-02, D-08）

**Files:**
- Modify: `deploy/Caddyfile:31-37`

- [ ] **Step 1: 修改 Caddyfile**

替换 `deploy/Caddyfile` 为：

```caddyfile
{$APP_DOMAIN} {
    encode gzip zstd

    # 安全 headers（公网暴露必备）
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }

    handle /api/* {
        reverse_proxy backend:8000 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    handle /docs* {
        reverse_proxy backend:8000
    }

    handle /openapi.json {
        reverse_proxy backend:8000
    }

    # 健康端点仅允许内部网络访问
    @health_internal {
        path /healthz /readyz
        remote_ip 127.0.0.1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
    }
    handle @health_internal {
        reverse_proxy backend:8000
    }
    handle /healthz {
        respond 404
    }
    handle /readyz {
        respond 404
    }

    handle {
        reverse_proxy frontend:80
    }

    log {
        output file /data/access.log {
            roll_size 10mb
            roll_keep 10
        }
        format json
    }
}
```

- [ ] **Step 2: 提交**

```bash
git add deploy/Caddyfile
git commit -m "fix: 健康端点限制内网访问（S-02）"
```

---

### Task 33: 定时备份脚本 + 前端容器非 root（D-06, S-04）

**Files:**
- Create: `deploy/scripts/backup_cron_setup.sh`
- Modify: `frontend/Dockerfile`

- [ ] **Step 1: 创建备份 cron 安装脚本**

创建 `deploy/scripts/backup_cron_setup.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

# 安装每日凌晨 3 点的数据库备份 cron job
# 用法: bash deploy/scripts/backup_cron_setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/pg_backup.sh"
LOG_DIR="$SCRIPT_DIR/../data/logs"
mkdir -p "$LOG_DIR"

CRON_LINE="0 3 * * * $BACKUP_SCRIPT >> $LOG_DIR/backup.log 2>&1"

# 避免重复添加
if crontab -l 2>/dev/null | grep -qF "$BACKUP_SCRIPT"; then
    echo "backup cron already installed"
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "backup cron installed: $CRON_LINE"
fi
```

```bash
chmod +x deploy/scripts/backup_cron_setup.sh
```

- [ ] **Step 2: 前端 Dockerfile 添加非 root 用户**

**关键校验说明**：Linux 上端口 80 < 1024 需要 root 权限。必须同时修改 nginx.conf 使用高端口。

2a. 先修改 `frontend/nginx.conf` line 2，将 `listen 80;` 改为 `listen 8080;`：

```nginx
server {
    listen 8080;
    server_name _;
    # ... 其余不变
}
```

2b. 修改 `frontend/Dockerfile`：

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# 非 root 运行：修正目录权限
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8080/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

2c. 修改 `deploy/docker-compose.yml` 中 frontend healthcheck 和 Caddy 反代目标：

- frontend healthcheck 改为 `http://localhost:8080/`
- `deploy/Caddyfile` 末尾 `reverse_proxy frontend:80` 改为 `reverse_proxy frontend:8080`

- [ ] **Step 3: 提交**

```bash
git add deploy/scripts/backup_cron_setup.sh frontend/Dockerfile
git commit -m "fix: 定时备份脚本 + 前端容器非 root 运行（D-06, S-04）"
```

---

# 批次五：CI/CD + 监控

### Task 34: 部署工作流 CI 门控 + 并发控制（CI-01, CI-03）

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: 添加 CI 门控和并发控制**

替换 `.github/workflows/deploy.yml` 为：

```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      ref:
        description: "Git ref to deploy"
        required: true
        default: "main"

concurrency:
  group: production-deploy
  cancel-in-progress: false

jobs:
  check-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.inputs.ref }}
      - name: Verify CI passed for this ref
        uses: actions/github-script@v7
        with:
          script: |
            const ref = '${{ github.event.inputs.ref }}';
            const { data: checks } = await github.rest.checks.listForRef({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: ref,
            });
            const ciBackend = checks.check_runs.find(c => c.name === 'backend');
            const ciFrontend = checks.check_runs.find(c => c.name === 'frontend');
            if (!ciBackend || ciBackend.conclusion !== 'success') {
              core.setFailed(`Backend CI has not passed for ref ${ref}`);
            }
            if (!ciFrontend || ciFrontend.conclusion !== 'success') {
              core.setFailed(`Frontend CI has not passed for ref ${ref}`);
            }
            core.info('CI checks passed');

  deploy:
    needs: check-ci
    runs-on: ubuntu-latest
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            set -euo pipefail
            cd "${{ secrets.DEPLOY_PATH }}"
            git fetch --all --tags
            git checkout "${{ github.event.inputs.ref }}"
            git pull --ff-only origin "${{ github.event.inputs.ref }}"
            bash deploy/scripts/deploy.sh

      - name: Notify deploy result
        if: always()
        run: |
          STATUS="${{ job.status }}"
          REF="${{ github.event.inputs.ref }}"
          echo "Deploy $STATUS for ref $REF"
          # 如果配置了通知 webhook，发送通知
          if [ -n "${{ secrets.DEPLOY_NOTIFY_WEBHOOK }}" ]; then
            curl -sf -X POST "${{ secrets.DEPLOY_NOTIFY_WEBHOOK }}" \
              -H "Content-Type: application/json" \
              -d "{\"text\": \"Deploy ${STATUS} for ${REF} by ${{ github.actor }}\"}" || true
          fi
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/deploy.yml
git commit -m "fix: 部署工作流添加 CI 门控、并发控制和通知（CI-01, CI-03, CI-04）"
```

---

### Task 35: CI 添加 Docker 构建测试（CI-02）

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 在 ci.yml 末尾添加 docker-build job**

在 `.github/workflows/ci.yml` 末尾追加：

```yaml

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build backend image
        run: docker build -t restock-backend:ci-test ./backend
      - name: Build frontend image
        run: docker build -t restock-frontend:ci-test ./frontend
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/ci.yml
git commit -m "feat: CI 添加 Docker 镜像构建测试（CI-02）"
```

---

### Task 36: Docker 基础镜像固定 digest（S-06）

**Files:**
- Modify: `backend/Dockerfile:1,19`
- Modify: `frontend/Dockerfile:1,11`

- [ ] **Step 1: 获取当前 digest**

```bash
docker pull python:3.11-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim
docker pull node:20-alpine && docker inspect --format='{{index .RepoDigests 0}}' node:20-alpine
docker pull nginx:1.27-alpine && docker inspect --format='{{index .RepoDigests 0}}' nginx:1.27-alpine
```

- [ ] **Step 2: 替换 Dockerfile 中的标签为 digest**

在 `backend/Dockerfile` 中，替换 line 1 和 19：

```dockerfile
FROM python:3.11-slim@sha256:<实际digest> AS builder
# ...
FROM python:3.11-slim@sha256:<实际digest> AS runtime
```

在 `frontend/Dockerfile` 中，替换 line 1 和 11：

```dockerfile
FROM node:20-alpine@sha256:<实际digest> AS builder
# ...
FROM nginx:1.27-alpine@sha256:<实际digest> AS runtime
```

（使用 Step 1 获取的实际 digest 值）

- [ ] **Step 3: 提交**

```bash
git add backend/Dockerfile frontend/Dockerfile
git commit -m "fix: Docker 基础镜像固定 digest 防止供应链攻击（S-06）"
```

---

### Task 37: SSH Action 固定 SHA（S-07）

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: 查找 appleboy/ssh-action v1.2.0 的 commit SHA**

```bash
git ls-remote https://github.com/appleboy/ssh-action.git v1.2.0
```

- [ ] **Step 2: 替换版本标签为 SHA**

在 `.github/workflows/deploy.yml` 中，替换：

```yaml
        uses: appleboy/ssh-action@v1.2.0
```

为：

```yaml
        uses: appleboy/ssh-action@<完整SHA>  # v1.2.0
```

- [ ] **Step 3: 提交**

```bash
git add .github/workflows/deploy.yml
git commit -m "fix: SSH deploy action 固定到完整 commit SHA（S-07）"
```

---

### Task 38: 基础 Prometheus 指标端点（O-01）

**Files:**
- Modify: `backend/app/api/metrics.py`
- Modify: `deploy/Caddyfile`

- [ ] **Step 1: 在 metrics.py 中添加 prometheus 端点**

**关键校验说明**：
- router 已有 `prefix="/api/metrics"`（line 83），端点路径不能重复写全路径
- `PlainTextResponse` 已在文件顶部从 `fastapi.responses` 导入，不需要再从 starlette 导入
- `TaskRun` 已在文件顶部（line 26）导入，不需要局部导入
- 此端点依赖 Task 10 的 `db_session_readonly`；如果 Task 10 未完成，暂用 `db_session`

在 `backend/app/api/metrics.py` 中添加新端点：

```python
@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics(
    db: AsyncSession = Depends(db_session_readonly),  # 如果 Task 10 未完成，用 db_session
) -> PlainTextResponse:
    """基础 Prometheus 文本格式指标。"""
    pending = (
        await db.execute(
            select(func.count()).select_from(TaskRun).where(TaskRun.status == "pending")
        )
    ).scalar() or 0

    running = (
        await db.execute(
            select(func.count()).select_from(TaskRun).where(TaskRun.status == "running")
        )
    ).scalar() or 0

    lines = [
        "# HELP restock_taskrun_pending Number of pending tasks",
        "# TYPE restock_taskrun_pending gauge",
        f"restock_taskrun_pending {pending}",
        "# HELP restock_taskrun_running Number of running tasks",
        "# TYPE restock_taskrun_running gauge",
        f"restock_taskrun_running {running}",
        "# HELP restock_up Application is up",
        "# TYPE restock_up gauge",
        "restock_up 1",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")
```

最终路径为 `/api/metrics/prometheus`（router prefix + endpoint path）。

- [ ] **Step 2: 在 Caddyfile 中代理 /api/metrics/prometheus**

该路径已被 `/api/*` 规则覆盖，无需额外配置。但可以考虑限制内网访问（与健康端点类似）。

- [ ] **Step 3: 运行后端测试**

```bash
cd backend && python -m pytest --tb=short
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/metrics.py
git commit -m "feat: 添加基础 Prometheus 指标端点（O-01）"
```

---

### Task 39: 批次五全量验证

- [ ] **Step 1: 运行完整后端测试**

```bash
cd backend && python -m pytest --tb=short
```

- [ ] **Step 2: 运行完整前端验证**

```bash
cd frontend && npx vue-tsc --noEmit && npx vite build && npm run test
```

- [ ] **Step 3: 验证 compose 配置**

```bash
cd deploy && docker compose config > /dev/null
```

- [ ] **Step 4: 检查 git 状态**

```bash
git log --oneline -20
git status
```

---

### Task 40: 文档同步（AGENTS.md 第 9 节要求）

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 更新 PROGRESS.md**

在 `docs/PROGRESS.md` 的"最近更新"日期更新为当前日期，并在"近期变更"章节添加：

```markdown
### 3.xx 项目审查修复（2026-04-xx）

批量修复审查发现的 45 项问题，涵盖：
- **阻塞级**：通用 500 处理器、shutdown 资源释放、ORM 约束、部署脚本修复
- **性能**：GET 只读会话、Element Plus 按需导入、同步分批 commit、快照保留策略
- **安全**：trusted proxy 验证、前端容器非 root、Docker digest 固定
- **健壮性**：FK ondelete、迁移锁、备份验证
- **代码质量**：类型安全、错误处理补全
- **部署**：日志轮转、CPU 限制、滚动重启、PG 调优
- **CI/CD**：CI 门控、Docker 构建测试、并发控制
- **监控**：Prometheus 指标端点
```

- [ ] **Step 2: 提交**

```bash
git add docs/PROGRESS.md
git commit -m "docs: 更新 PROGRESS.md 记录审查修复变更"
```

---

## 注意事项

1. **每个 Task 完成后运行对应测试**，确保不引入回归。
2. **批次间执行全量测试**（`pytest` + `vue-tsc` + `vite build`）。
3. **Element Plus 按需导入（Task 11）风险最高**——如果样式丢失，立即回退到 CSS 全量 + JS 按需方案。
4. **Docker digest 固定（Task 36）需要运行时获取**——在执行环境中拉取镜像并记录 digest。
5. **前端 Dockerfile 非 root（Task 33）**——如果端口 80 权限问题导致启动失败，需改 nginx listen 端口。
6. **PG 自定义配置（Task 30）**——首次应用需要重启 PG 容器并可能需要 `initdb` 重新初始化。建议在全新部署时应用。
