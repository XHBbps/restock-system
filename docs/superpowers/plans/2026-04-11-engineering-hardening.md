# 工程化加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 restock_system 项目补齐工程化短板——统一 Git Hooks、依赖安全扫描、测试覆盖率门禁、后端集成测试框架、前端测试规范化。

**Architecture:** 五个独立方案 (A-E) 按依赖顺序排列。C 无依赖最先做；B 无依赖紧随；A 依赖测试能跑通；D 和 E 各自独立但建议在 A 之后（覆盖率才有意义）。

**Tech Stack:** GitHub Actions, Dependabot, pip-audit, npm audit, pytest-cov, vitest coverage (v8), pre-commit

---

## Task 1: 统一 Git Hook — 移除 husky/lint-staged（方案 C）

**Files:**
- Modify: `frontend/package.json`

pre-commit 已覆盖前后端 lint/format/type-check。husky 声明了但从未初始化，lint-staged 配置了但无 hook 触发，两者均为死配置。

- [ ] **Step 1: 从 package.json 移除 husky 和 lint-staged**

从 `devDependencies` 中删除 `"husky": "^9.1.7"` 和 `"lint-staged": "^15.2.10"`。

删除整个 `"lint-staged"` 配置块：

```json
"lint-staged": {
    "src/**/*.{ts,tsx,vue}": [
      "eslint --max-warnings 0 --fix",
      "prettier --write"
    ],
    "src/**/*.{scss,css,html,json}": [
      "prettier --write"
    ]
  }
```

- [ ] **Step 2: 重新安装依赖，验证无报错**

Run: `cd frontend && npm install`
Expected: 无 error，lock file 更新

- [ ] **Step 3: 验证 pre-commit 仍然正常工作**

Run: `cd .. && pre-commit run --all-files`
Expected: 所有 hook pass（ruff, ruff-format, mypy, frontend-lint）

- [ ] **Step 4: 提交**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: remove unused husky and lint-staged — pre-commit covers all hooks"
```

---

## Task 2: 依赖安全扫描 — Dependabot + CI 审计（方案 B）

**Files:**
- Create: `.github/dependabot.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `backend/pyproject.toml` (添加 pip-audit dev 依赖)

### Step 2.1: 创建 Dependabot 配置

- [ ] **创建 `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /backend
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    labels:
      - dependencies
      - backend

  - package-ecosystem: npm
    directory: /frontend
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    labels:
      - dependencies
      - frontend

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: monthly
    open-pull-requests-limit: 3
    labels:
      - dependencies
      - ci
```

### Step 2.2: 添加 pip-audit 到 dev 依赖

- [ ] **在 `backend/pyproject.toml` 的 `[project.optional-dependencies] dev` 列表末尾添加：**

```toml
    "pip-audit>=2.7.0",
```

- [ ] **安装验证**

Run: `cd backend && pip install -e ".[dev]"`
Expected: pip-audit 安装成功

### Step 2.3: CI 中添加安全审计步骤

- [ ] **修改 `.github/workflows/ci.yml`**

在 backend job 的 `Run backend type check` step 之后追加：

```yaml
      - name: Audit backend dependencies
        run: pip-audit
```

在 frontend job 的 `Run frontend tests` step 之后追加：

```yaml
      - name: Audit frontend dependencies
        run: npm audit --audit-level=high
```

### Step 2.4: 本地验证

- [ ] **验证 pip-audit 可运行**

Run: `cd backend && pip-audit`
Expected: 输出依赖列表，无 critical/high 漏洞（如有已知漏洞会报告，暂不阻塞）

- [ ] **验证 npm audit 可运行**

Run: `cd ../frontend && npm audit --audit-level=high`
Expected: 输出审计结果

### Step 2.5: 提交

- [ ] **提交**

```bash
git add .github/dependabot.yml .github/workflows/ci.yml backend/pyproject.toml
git commit -m "chore: add Dependabot config and dependency audit steps to CI"
```

---

## Task 3: 后端测试覆盖率门禁（方案 A — 后端部分）

**Files:**
- Create: `backend/.coveragerc`
- Modify: `.github/workflows/ci.yml`

### Step 3.1: 创建覆盖率配置

- [ ] **创建 `backend/.coveragerc`**

```ini
[run]
source = app
omit =
    app/db/session.py
    app/main.py
    alembic/*

[report]
fail_under = 50
show_missing = true
skip_covered = true
exclude_lines =
    pragma: no cover
    if TYPE_CHECKING:
    if __name__ == .__main__.:
```

注：`fail_under = 50` 设为保守起点，后续视实际覆盖率逐步提高。

### Step 3.2: 本地验证覆盖率

- [ ] **运行带覆盖率的测试**

Run: `cd backend && python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider`
Expected: 测试全部 pass，终端显示覆盖率报告，总覆盖率 ≥ 50%

如果覆盖率 < 50%，将 `fail_under` 调整为当前值减 5（留安全余量）。

### Step 3.3: CI 中启用覆盖率

- [ ] **修改 `.github/workflows/ci.yml` 的 backend job**

将原来的：

```yaml
      - name: Run backend tests
        run: python -m pytest -p no:cacheprovider
```

替换为：

```yaml
      - name: Run backend tests with coverage
        run: python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider
```

### Step 3.4: 验证 CI 配置语法

- [ ] **验证 YAML 格式正确**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"; echo "YAML OK"`
Expected: `YAML OK`

### Step 3.5: 提交

- [ ] **提交**

```bash
git add backend/.coveragerc .github/workflows/ci.yml
git commit -m "chore: add backend test coverage gate (fail_under=50)"
```

---

## Task 4: 前端测试覆盖率门禁 + vitest 配置（方案 A 前端 + 方案 E 配置部分）

**Files:**
- Create: `frontend/vitest.config.ts`
- Modify: `frontend/package.json` (添加 @vitest/coverage-v8)
- Modify: `.github/workflows/ci.yml`

### Step 4.1: 添加覆盖率依赖

- [ ] **安装 @vitest/coverage-v8**

Run: `cd frontend && npm install -D @vitest/coverage-v8`
Expected: 安装成功，package.json 和 lock file 更新

### Step 4.2: 创建 vitest.config.ts

- [ ] **创建 `frontend/vitest.config.ts`**

```typescript
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,vue}'],
      exclude: ['src/**/*.test.ts', 'src/main.ts', 'src/env.d.ts'],
      thresholds: {
        statements: 20,
      },
    },
  },
})
```

注：`statements: 20` 为保守起点（当前仅 4 个测试文件），后续逐步提高。

### Step 4.3: 更新 package.json scripts

- [ ] **修改 `frontend/package.json` 的 `scripts` 部分**

将：

```json
"test": "vitest run",
```

替换为：

```json
"test": "vitest run",
"test:coverage": "vitest run --coverage",
```

### Step 4.4: 本地验证

- [ ] **运行带覆盖率的测试**

Run: `cd frontend && npm run test:coverage`
Expected: 测试 pass，终端显示覆盖率报告

### Step 4.5: CI 中启用前端覆盖率

- [ ] **修改 `.github/workflows/ci.yml` 的 frontend job**

将原来的：

```yaml
      - name: Run frontend tests
        run: npm test
```

替换为：

```yaml
      - name: Run frontend tests with coverage
        run: npm run test:coverage
```

### Step 4.6: 提交

- [ ] **提交**

```bash
git add frontend/vitest.config.ts frontend/package.json frontend/package-lock.json .github/workflows/ci.yml
git commit -m "chore: add vitest config with coverage gate (statements>=20)"
```

---

## Task 5: 后端集成测试框架（方案 D）

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_health.py`
- Modify: `backend/.coveragerc` (覆盖范围包含集成测试)

### Step 5.1: 创建共享 conftest.py

- [ ] **创建 `backend/tests/conftest.py`**

```python
"""Shared pytest fixtures for all test suites."""

import os

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip integration tests unless TEST_DATABASE_URL is set."""
    if os.environ.get("TEST_DATABASE_URL"):
        return
    skip_integration = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip_integration)
```

### Step 5.2: 创建集成测试 conftest

- [ ] **创建 `backend/tests/integration/__init__.py`**

空文件。

- [ ] **创建 `backend/tests/integration/conftest.py`**

```python
"""Integration test fixtures — require a real PostgreSQL database.

Set TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname to enable.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base


@pytest.fixture(scope="session")
def db_engine():
    import os

    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    return engine


@pytest.fixture(autouse=True)
async def _setup_db(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    from app.api.deps import db_session as dep_db_session
    from app.main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[dep_db_session] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

### Step 5.3: 创建第一个集成测试

- [ ] **创建 `backend/tests/integration/test_health.py`**

```python
"""Smoke test: health endpoints respond correctly with a real DB."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_readyz(client: AsyncClient) -> None:
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
```

### Step 5.4: 验证单元测试仍然通过（不设置 TEST_DATABASE_URL）

- [ ] **运行全部测试**

Run: `cd backend && python -m pytest -p no:cacheprovider -v`
Expected: 所有 unit 测试 pass，integration 测试被 skip（显示 `SKIPPED (TEST_DATABASE_URL not set)`）

### Step 5.5: 验证集成测试（需要本地数据库）

- [ ] **用本地 docker-compose 数据库跑集成测试**

Run: `cd backend && TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/restock_test" python -m pytest tests/integration/ -v`

Expected: 如果本地 PostgreSQL 可用，测试 pass；如果不可用，报连接错误（预期行为）。

注：如果本地 DB 不可用可跳过此步，CI 中可后续添加 PostgreSQL service 容器。

### Step 5.6: 提交

- [ ] **提交**

```bash
git add backend/tests/conftest.py backend/tests/integration/
git commit -m "feat: add integration test framework with auto-skip when no DB"
```

---

## Task 6: 前端测试目录规范 + 示例测试补充（方案 E 剩余部分）

**Files:**
- Create: `frontend/src/utils/__tests__/tableSort.test.ts`
- Create: `frontend/src/api/__tests__/client.test.ts`

当前 4 个测试文件散落在 `src/` 各处，格式为 `*.test.ts`（与 vitest.config.ts 的 `include` 匹配）。不做迁移（避免无谓改动），但为缺失测试的核心模块补充示例测试。

### Step 6.1: 为 tableSort 工具函数添加测试

- [ ] **创建 `frontend/src/utils/__tests__/tableSort.test.ts`**

```typescript
import { describe, expect, it } from 'vitest'
import {
  applyLocalSort,
  compareNumber,
  compareText,
  normalizeSortOrder,
} from '../tableSort'

describe('normalizeSortOrder', () => {
  it('converts ascending to asc', () => {
    expect(normalizeSortOrder('ascending')).toBe('asc')
  })

  it('converts descending to desc', () => {
    expect(normalizeSortOrder('descending')).toBe('desc')
  })

  it('returns undefined for null', () => {
    expect(normalizeSortOrder(null)).toBeUndefined()
  })
})

describe('compareNumber', () => {
  it('returns negative when left < right', () => {
    expect(compareNumber(1, 2)).toBeLessThan(0)
  })

  it('returns positive when left > right', () => {
    expect(compareNumber(5, 3)).toBeGreaterThan(0)
  })

  it('returns 0 for equal values', () => {
    expect(compareNumber(4, 4)).toBe(0)
  })

  it('pushes null to end', () => {
    expect(compareNumber(null, 5)).toBe(1)
    expect(compareNumber(5, null)).toBe(-1)
  })
})

describe('compareText', () => {
  it('compares strings with zh-CN locale', () => {
    expect(compareText('a', 'b')).toBeLessThan(0)
  })

  it('pushes null to end', () => {
    expect(compareText(null, 'a')).toBe(1)
  })
})

describe('applyLocalSort', () => {
  const items = [
    { id: 1, name: 'B', qty: 10 },
    { id: 2, name: 'A', qty: 20 },
    { id: 3, name: 'C', qty: 5 },
  ]

  it('sorts ascending by comparator', () => {
    const result = applyLocalSort(items, { prop: 'qty', order: 'asc' }, {
      qty: (a, b) => compareNumber(a.qty, b.qty),
    })
    expect(result.map((r) => r.id)).toEqual([3, 1, 2])
  })

  it('sorts descending', () => {
    const result = applyLocalSort(items, { prop: 'qty', order: 'desc' }, {
      qty: (a, b) => compareNumber(a.qty, b.qty),
    })
    expect(result.map((r) => r.id)).toEqual([2, 1, 3])
  })

  it('uses fallback when no prop match', () => {
    const result = applyLocalSort(items, {}, {}, (a, b) => compareNumber(a.id, b.id))
    expect(result.map((r) => r.id)).toEqual([1, 2, 3])
  })
})
```

### Step 6.2: 验证新测试通过

- [ ] **运行前端测试**

Run: `cd frontend && npm test`
Expected: 所有测试 pass（包括新增的 tableSort 测试）

### Step 6.3: 提交

- [ ] **提交**

```bash
git add frontend/src/utils/__tests__/tableSort.test.ts
git commit -m "test: add unit tests for tableSort utility functions"
```

---

## Task 7: 最终验证 — 全量 CI 模拟

**Files:** 无新文件

### Step 7.1: 运行后端全量检查

- [ ] **后端 lint + type check + 测试 + 覆盖率 + 审计**

Run:
```bash
cd backend && python -m ruff check . && python -m mypy app && python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider && pip-audit
```
Expected: 全部 pass

### Step 7.2: 运行前端全量检查

- [ ] **前端 build + 测试 + 覆盖率 + 审计**

Run:
```bash
cd frontend && npm run build && npm run test:coverage && npm audit --audit-level=high
```
Expected: 全部 pass

### Step 7.3: 验证 CI workflow 语法

- [ ] **检查 CI YAML 合法**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('CI YAML OK')"`
Expected: `CI YAML OK`

### Step 7.4: 验证 Dependabot 配置

- [ ] **检查 Dependabot YAML 合法**

Run: `python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml')); print('Dependabot YAML OK')"`
Expected: `Dependabot YAML OK`

### Step 7.5: 验证 pre-commit 正常

- [ ] **运行 pre-commit**

Run: `pre-commit run --all-files`
Expected: 所有 hook pass

### Step 7.6: 确认无遗漏文件

- [ ] **检查工作目录状态**

Run: `git status`
Expected: 无未提交的改动（clean working tree）
