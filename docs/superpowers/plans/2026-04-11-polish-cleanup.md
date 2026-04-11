# 最小化收尾打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 `.env.example` 配置、给 2 个未分页端点加上限保护、清理 pytest socket 泄漏告警、完善 pre-commit 配置校验。

**Architecture:**
- **Part A (Task 1, 必做)**: 修正 `.env.example` 与 `config.py` 的偏差（13 个缺失变量 + 1 个已删除但仍残留的变量）
- **Part B (Task 2-3, 推荐)**: 给 `/api/data/warehouses` 和 `/api/data/shops` 添加可选分页参数，保持向后兼容
- **Part C (Task 4, 可选)**: 诊断并尝试修复 pytest socket 泄漏告警
- **Part D (Task 5, 可选)**: 添加 `check-toml` + `check-json` pre-commit hooks
- **Final (Task 6)**: 全量验证

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy（后端），pre-commit，pytest

**Scope exclusion:** `/api/data/sync-state` 返回 `list[DataSyncStateRow]`（无包装），是一个固定的小集合（每个 sync job 一行，~10 条），改成分页会破坏前端契约且收益为零。**明确不做**。

---

## Task 1: 补全 .env.example（Part A）

**Files:**
- Modify: `backend/.env.example`

**Problem:** `.env.example` 有 28 行，而 `config.py` 定义了 ~30 个 settings 字段。对比发现：
- **缺失** 13 个变量：`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`, `SAIHU_REQUEST_TIMEOUT_SECONDS`, `SAIHU_MAX_RETRIES`, `SAIHU_TOKEN_REFRESH_AHEAD_SECONDS`, `LOGIN_FAILED_MAX`, `LOGIN_LOCK_MINUTES`, `DEFAULT_BUFFER_DAYS`, `DEFAULT_TARGET_DAYS`, `DEFAULT_LEAD_TIME_DAYS`, `DEFAULT_CALC_CRON`, `DEFAULT_SYNC_INTERVAL_MINUTES`
- **残留** 1 个已删除的变量：`SAIHU_RATE_LIMIT_QPS=1`（之前的死代码清理已从 config.py 移除，但 .env.example 仍在）

### Step 1.1: 覆写 .env.example

- [ ] **替换整个文件内容**

将 `backend/.env.example` 完整替换为：

```env
# ============================================================
# 应用基础
# ============================================================
APP_NAME=restock_backend
APP_ENV=development
APP_TIMEZONE=Asia/Shanghai
APP_LOG_LEVEL=INFO
APP_DOCS_ENABLED=true

# ============================================================
# 数据库
# ============================================================
DATABASE_URL=postgresql+asyncpg://postgres:change_me@db:5432/replenish
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_POOL_RECYCLE_SECONDS=3600

# ============================================================
# 赛狐 API
# ============================================================
SAIHU_BASE_URL=https://openapi.sellfox.com
SAIHU_CLIENT_ID=your_client_id
SAIHU_CLIENT_SECRET=your_client_secret
SAIHU_REQUEST_TIMEOUT_SECONDS=30
SAIHU_MAX_RETRIES=3
SAIHU_TOKEN_REFRESH_AHEAD_SECONDS=300

# ============================================================
# 认证 / 登录
# ============================================================
LOGIN_PASSWORD=please_change_me
JWT_SECRET=generate_with_openssl_rand_base64_32
JWT_EXPIRES_HOURS=24
LOGIN_FAILED_MAX=5
LOGIN_LOCK_MINUTES=10

# ============================================================
# 后台进程开关
# ============================================================
PROCESS_ENABLE_WORKER=true
PROCESS_ENABLE_REAPER=true
PROCESS_ENABLE_SCHEDULER=true

# ============================================================
# Worker / Reaper
# ============================================================
WORKER_POLL_INTERVAL_SECONDS=2
WORKER_LEASE_MINUTES=2
WORKER_HEARTBEAT_SECONDS=30
REAPER_INTERVAL_SECONDS=60

# ============================================================
# 推送重试
# ============================================================
PUSH_AUTO_RETRY_TIMES=3
PUSH_MAX_ITEMS_PER_BATCH=50

# ============================================================
# 默认业务参数（可在 /api/config/global 运行时覆盖）
# ============================================================
DEFAULT_BUFFER_DAYS=30
DEFAULT_TARGET_DAYS=60
DEFAULT_LEAD_TIME_DAYS=50
DEFAULT_CALC_CRON=0 8 * * *
DEFAULT_SYNC_INTERVAL_MINUTES=60
```

**关键差异说明：**
- 删掉了 `SAIHU_RATE_LIMIT_QPS=1`（已从 config.py 移除）
- 新增 13 个变量，按业务分组组织
- 注释用中文分段分组（与项目其他文件风格一致）

### Step 1.2: 验证 .env.example 与 config.py 完全同步

- [ ] **运行校验脚本**

```bash
cd E:/Ai_project/restock_system && python -c "
import re

# Read config.py Settings class fields
with open('backend/app/config.py', 'r', encoding='utf-8') as f:
    config = f.read()

# Extract field names from the Settings class (pattern: 'name: type = ...')
settings_fields = set()
in_settings = False
for line in config.splitlines():
    stripped = line.strip()
    if 'class Settings' in line:
        in_settings = True
        continue
    if in_settings:
        if stripped.startswith('def '):
            break
        m = re.match(r'([a-z_][a-z0-9_]*)\s*:', stripped)
        if m:
            settings_fields.add(m.group(1).upper())

# Read .env.example keys
with open('backend/.env.example', 'r', encoding='utf-8') as f:
    env_lines = f.read().splitlines()

env_keys = set()
for line in env_lines:
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        env_keys.add(line.split('=', 1)[0])

# Compare
in_config_not_env = settings_fields - env_keys
in_env_not_config = env_keys - settings_fields

print(f'Settings in config.py: {len(settings_fields)}')
print(f'Keys in .env.example:  {len(env_keys)}')
print(f'')
print(f'Missing from .env.example: {sorted(in_config_not_env)}')
print(f'Stale in .env.example:     {sorted(in_env_not_config)}')
"
```

Expected: `Missing from .env.example: []` and `Stale in .env.example: []`

**注意**: `config.py` 中的 `jwt_algorithm`（固定为 HS256，通常不需要配置）可能不在 .env.example 里——可以接受。如果 diff 结果只剩 `JWT_ALGORITHM` 且仅在 config.py 中，那是可以的。其他任何缺失都必须修复。

### Step 1.3: 验证后端仍能启动

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -c "from app.config import get_settings; s = get_settings(); print('OK:', s.app_name)"`
Expected: `OK: restock_backend`

### Step 1.4: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/.env.example
git commit -m "docs(env): sync .env.example with config.py (add 13 missing vars, remove stale SAIHU_RATE_LIMIT_QPS)"
```

---

## Task 2: 给 /api/data/warehouses 加分页（Part B1）

**Files:**
- Modify: `backend/app/api/data.py` (第 586-626 行 `list_data_warehouses`)
- Modify: `backend/app/schemas/data.py` (第 159-162 行 `DataWarehouseListOut`)

**Strategy:** 添加可选 `page` + `page_size` query 参数（默认 `page=1, page_size=500`），后端用 `.limit().offset()` 分页，`total` 通过单独 COUNT 查询获取。前端当前调用时不传这两个参数，会拿到默认的 500 条——对 1-5 人项目的仓库数量完全够用，零破坏。

### Step 2.1: 修改 DataWarehouseListOut schema

- [ ] **编辑 `backend/app/schemas/data.py`**

找到第 159-162 行：
```python
class DataWarehouseListOut(BaseModel):
    items: list[DataWarehouse]
    total: int
```

替换为：
```python
class DataWarehouseListOut(BaseModel):
    items: list[DataWarehouse]
    total: int
    page: int = 1
    page_size: int = 500

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
```

**说明**：
- `page` 和 `page_size` 有默认值，老调用者不提供时不会报错
- `model_config` 保证 camelCase 别名，与其他 ListOut 一致

### Step 2.2: 修改 list_data_warehouses endpoint

- [ ] **编辑 `backend/app/api/data.py` 的 `list_data_warehouses`**

找到第 586-626 行整段 `list_data_warehouses` 函数，替换为：

```python
@router.get("/warehouses", response_model=DataWarehouseListOut)
async def list_data_warehouses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataWarehouseListOut:
    stock_subquery = (
        select(
            InventorySnapshotLatest.warehouse_id.label("warehouse_id"),
            func.coalesce(
                func.sum(InventorySnapshotLatest.available + InventorySnapshotLatest.reserved),
                0,
            ).label("total_stock"),
        )
        .group_by(InventorySnapshotLatest.warehouse_id)
        .subquery()
    )

    total = (await db.execute(select(func.count()).select_from(Warehouse))).scalar_one()

    rows = (
        await db.execute(
            select(
                Warehouse,
                func.coalesce(stock_subquery.c.total_stock, 0).label("total_stock"),
            )
            .outerjoin(stock_subquery, stock_subquery.c.warehouse_id == Warehouse.id)
            .order_by(Warehouse.country, Warehouse.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    items = [
        DataWarehouse.model_validate(
            {
                "id": warehouse.id,
                "name": warehouse.name,
                "type": warehouse.type,
                "country": warehouse.country,
                "replenish_site": warehouse.replenish_site_raw,
                "total_stock": int(total_stock or 0),
                "last_sync_at": warehouse.last_sync_at,
            }
        )
        for warehouse, total_stock in rows
    ]
    return DataWarehouseListOut(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )
```

### Step 2.3: 确认 Query 已在 imports 中

- [ ] **验证**

Run: `cd E:/Ai_project/restock_system && grep "from fastapi import" backend/app/api/data.py | head -1`
Expected: 输出的 import 行应包含 `Query`（若已是 `from fastapi import APIRouter, Depends, Path, Query` 之类即可）。

如果没有 `Query`，补充到导入列表中。

### Step 2.4: 运行相关测试

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest tests/unit/test_data_warehouses_api.py -v -p no:cacheprovider 2>&1 | tail -10`
Expected: 所有测试 pass

**注意**：如果现有测试 mock 了固定的 `_FakeDb` responses 且没预期到新增的 `count` 查询，可能会失败。这时需要给 mock 加一条 `count` 响应。具体方式：在 `_FakeDb` 的 responses 列表前面插入一条 `_ScalarResult(N)` 其中 `N` 是期望的总数。

### Step 2.5: 运行完整后端测试

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest -p no:cacheprovider 2>&1 | tail -3`
Expected: `133 passed, 2 skipped`（和之前一样）

### Step 2.6: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/app/api/data.py backend/app/schemas/data.py
git commit -m "feat(api): add pagination params to GET /api/data/warehouses"
```

---

## Task 3: 给 /api/data/shops 加分页（Part B2）

**Files:**
- Modify: `backend/app/api/data.py` (第 632-639 行 `list_data_shops`)
- Modify: `backend/app/schemas/data.py` (第 177-179 行 `DataShopListOut`)

### Step 3.1: 修改 DataShopListOut schema

- [ ] **编辑 `backend/app/schemas/data.py`**

找到第 177-179 行：
```python
class DataShopListOut(BaseModel):
    items: list[DataShop]
    total: int
```

替换为：
```python
class DataShopListOut(BaseModel):
    items: list[DataShop]
    total: int
    page: int = 1
    page_size: int = 500

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
```

### Step 3.2: 修改 list_data_shops endpoint

- [ ] **编辑 `backend/app/api/data.py`**

找到第 632-639 行：
```python
@router.get("/shops", response_model=DataShopListOut)
async def list_data_shops(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataShopListOut:
    rows = (await db.execute(select(Shop).order_by(Shop.marketplace_id, Shop.id))).scalars().all()
    items = [DataShop.model_validate(r) for r in rows]
    return DataShopListOut(items=items, total=len(items))
```

替换为：
```python
@router.get("/shops", response_model=DataShopListOut)
async def list_data_shops(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataShopListOut:
    total = (await db.execute(select(func.count()).select_from(Shop))).scalar_one()
    rows = (
        await db.execute(
            select(Shop)
            .order_by(Shop.marketplace_id, Shop.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).scalars().all()
    items = [DataShop.model_validate(r) for r in rows]
    return DataShopListOut(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )
```

### Step 3.3: 运行完整后端测试

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest -p no:cacheprovider 2>&1 | tail -3`
Expected: `133 passed, 2 skipped`

如果新加的 count 查询破坏了 mock，同样在 `_FakeDb` 前插入一条 `_ScalarResult`。

### Step 3.4: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/app/api/data.py backend/app/schemas/data.py
git commit -m "feat(api): add pagination params to GET /api/data/shops"
```

---

## Task 4: 诊断并尝试修复 pytest socket 泄漏告警（Part C，可选）

**Files:** 需先诊断再确定

**Problem:** 运行 `pytest` 时输出：
```
PytestUnraisableExceptionWarning: Exception ignored in: <socket.socket fd=948, family=2, type=1, proto=0, laddr=('127.0.0.1', 7739), raddr=('127.0.0.1', 7738)>
ResourceWarning: unclosed <socket.socket ...>
```

测试全部 pass，但这意味着某个测试里 `httpx.AsyncClient` 或其他 async HTTP 对象没有被正确关闭。本 Task 是"尝试修复"，如果 30 分钟内定位不到，**放弃此 Task** 并在总结里报告 `DONE_WITH_CONCERNS: 遗留 asyncio 告警未修复`。

### Step 4.1: 定位泄漏源

- [ ] **搜索可疑的 httpx/aiohttp 使用**

Run: `cd E:/Ai_project/restock_system && grep -rn "AsyncClient\|aiohttp\|httpx" backend/tests/ 2>&1`

记录所有结果。重点关注有没有 fixture 或直接实例化 `AsyncClient()` 却没用 `async with`。

### Step 4.2: 逐测试文件排查定位

- [ ] **运行各测试文件并观察哪个产生 socket 泄漏**

对 `tests/unit/` 下每个文件：

```bash
for f in backend/tests/unit/test_*.py; do
    echo "=== $f ==="
    cd E:/Ai_project/restock_system/backend && python -m pytest "$f" -p no:cacheprovider 2>&1 | grep -E "Resource|socket|FAILED|passed" | tail -3
    cd E:/Ai_project/restock_system
done
```

记录哪些文件输出 `ResourceWarning: unclosed socket`。

### Step 4.3: 基于诊断结果修复

**如果定位到源头（例如某测试创建 httpx AsyncClient 没关闭）**，修改该测试使用正确的 async context manager：

```python
# Before (leak)
client = AsyncClient(...)
response = await client.get(...)

# After (no leak)
async with AsyncClient(...) as client:
    response = await client.get(...)
```

**如果是 bcrypt 或其他 C 扩展导致的假阳性**，在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 下的 `filterwarnings` 里加一条忽略：

```toml
filterwarnings = [
    "error",
    "ignore::pytest.PytestUnraisableExceptionWarning",
]
```

**注意**：忽略 warning 是最后手段，优先修真实泄漏。

### Step 4.4: 验证告警消失

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest -p no:cacheprovider 2>&1 | grep -i "ResourceWarning\|PytestUnraisableExceptionWarning"`
Expected: 无输出

### Step 4.5: 提交（如果找到修复）

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add <修改的文件>
git commit -m "fix(test): close async HTTP client properly to prevent socket leak"
```

**如果没找到修复**，跳过此 Task 并在 Task 6 报告里说明。

---

## Task 5: Pre-commit 添加 check-toml / check-json（Part D）

**Files:**
- Modify: `.pre-commit-config.yaml`

### Step 5.1: 修改 .pre-commit-config.yaml

- [ ] **编辑 `.pre-commit-config.yaml`**

找到 `pre-commit/pre-commit-hooks` 的 hook 列表（第 5-16 行），在 `check-yaml` 和 `check-added-large-files` 之间插入 `check-toml` 和 `check-json`：

将：
```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \.md$
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ["--maxkb=500"]
      - id: check-merge-conflict
      - id: mixed-line-ending
        args: ["--fix=lf"]
```

替换为：
```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        exclude: \.md$
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
        exclude: \.secrets\.baseline$|package-lock\.json$|tsconfig.*\.json$
      - id: check-added-large-files
        args: ["--maxkb=500"]
      - id: check-merge-conflict
      - id: mixed-line-ending
        args: ["--fix=lf"]
```

**说明**：
- `check-toml` 校验所有 `.toml` 文件语法
- `check-json` 校验所有 `.json` 文件——`.secrets.baseline` 是 detect-secrets 的特殊文件，`package-lock.json` 过大跑得慢，`tsconfig*.json` 允许 JSONC（带注释的 JSON，标准 check-json 会拒绝）

### Step 5.2: 验证 YAML 语法正确

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system && python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml', encoding='utf-8')); print('YAML OK')"`
Expected: `YAML OK`

### Step 5.3: 测试新 hook 实际可用

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system && pre-commit run check-toml check-json --all-files 2>&1 | tail -15`
Expected: 两个 hook 都显示 `Passed`

如果 `check-json` 在 `.secrets.baseline` 或其他 JSONC 文件上失败，扩展 `exclude` 模式。

### Step 5.4: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add .pre-commit-config.yaml
git commit -m "chore(pre-commit): add check-toml and check-json validation hooks"
```

---

## Task 6: 最终全量验证

- [ ] **后端 ruff**

Run: `cd E:/Ai_project/restock_system/backend && python -m ruff check . 2>&1 | tail -3`
Expected: `All checks passed!`

- [ ] **后端 mypy**

Run: `cd E:/Ai_project/restock_system/backend && python -m mypy app 2>&1 | tail -3`
Expected: `Success: no issues found in 87 source files`

- [ ] **后端测试 + 覆盖率**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest --cov --cov-config=.coveragerc --cov-report=term -p no:cacheprovider 2>&1 | tail -3`
Expected: 133+ passed, 2 skipped, 覆盖率 ≥ 55%

- [ ] **Alembic 单 head**

Run: `cd E:/Ai_project/restock_system/backend && python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config('alembic.ini')
s = ScriptDirectory.from_config(c)
assert len(s.get_heads()) == 1
print('OK')
"`
Expected: `OK`

- [ ] **.env.example 同步校验**

Run: 重复 Task 1 Step 1.2 的校验脚本
Expected: `Missing from .env.example: []`（或只包含 `JWT_ALGORITHM`）

- [ ] **前端 lint + type-check + test**

Run: `cd E:/Ai_project/restock_system/frontend && npm run lint && npm run type-check && npm test 2>&1 | tail -5`
Expected: 全部 pass，33 tests passed

- [ ] **Pre-commit 全量运行**

Run: `cd E:/Ai_project/restock_system && pre-commit run --all-files 2>&1 | tail -20`
Expected: 所有 hook（包括新加的 check-toml + check-json）pass

- [ ] **git 状态**

Run: `cd E:/Ai_project/restock_system && git status --short`
Expected: 无未提交改动

---

## Self-Review

### Spec coverage
- ✅ A `.env.example` 补全 → Task 1
- ✅ B1 warehouses 分页 → Task 2
- ✅ B2 shops 分页 → Task 3
- ✅ C asyncio socket 泄漏 → Task 4（尝试修，允许放弃）
- ✅ D pre-commit 新 hook → Task 5
- ❌ sync-state 分页 — **明确不做**，已在 Architecture 节说明理由

### Risk notes
- **Task 2/3** 添加了 `count` 查询，理论上轻微增加每次请求的 DB 压力——对 warehouses/shops 这种小表忽略不计。
- **Task 2/3** 可能破坏 `test_data_warehouses_api.py` 等依赖 mock 固定响应列表的测试。Step 2.4 提前预警了这种情况。
- **Task 4** 可能找不到根因，计划明确允许放弃。
- **Task 5** 的 `check-json` 默认不支持 JSONC（带注释），需要通过 `exclude` 跳过 `tsconfig*.json`。

### Type consistency
- `DataWarehouseListOut` 和 `DataShopListOut` 都添加了 `page: int = 1, page_size: int = 500`，前端 `{ items: [], total: N }` 接口契约保持兼容（新字段前端不读也不报错）。
- Task 2 和 Task 3 使用一致的 `ge=1, le=1000, default=500` 参数约束。
