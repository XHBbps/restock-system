# 真实 Bug 修复 + 核心业务测试 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复真实运行时 bug（测试污染 + alembic 两个 heads），补齐补货引擎和安全模块的核心测试，加防御性 fixture 预防未来污染。

**Architecture:**
- **Part α (Task 1-2, 必做)**：修真 bug。Task 1 消除 `importlib.reload` 引起的类对象身份污染；Task 2 合并 alembic migration 的两个 heads。
- **Part β (Task 3-4, 强烈推荐)**：核心业务测试。`engine/runner.py` 24% → 55%+；`core/security.py` 42% → 85%+。
- **Part γ (Task 5, 可选)**：`conftest.py` 加 `get_settings.cache_clear()` autouse fixture 作防御层。
- **Final (Task 6)**：全量验证。

**Tech Stack:** pytest + pytest-asyncio + pytest-mock（后端），Alembic（数据库迁移）

---

## Part α: 修真 Bug

### Task 1: 修复 test_health_endpoints.py 的 importlib.reload 污染

**Files:**
- Modify: `backend/tests/unit/test_health_endpoints.py`

**Root cause (已验证):** `test_health_endpoints.py` 的 4 个测试都用 `importlib.reload(main_module)` 重新加载 `app.main`。这个 reload 级联到 `app.core.exceptions` 等模块——当它们被重载后，`SaihuAPIError` 类在 Python 内存里变成了**一个新的类对象**。之后 `test_pushback_purchase.py::test_push_saihu_job_failure_writes_error` 创建的 `SaihuAPIError("server error")` 用的是**旧类**；而 `purchase.py` 里 `except SaihuAPIError as exc:` 捕获的是**新类**。`isinstance` 检查失败，异常没被 except 捕获，测试断言 `db2.commits == 2` 失败（因为没执行到 DB 更新分支）。

**修复策略:** 不再调用 `importlib.reload`。测试真正需要的是"`app.main` 模块已加载"——这在 import 时就已经满足。`monkeypatch.setenv("APP_ENV", "development")` 对 `readyz` 的直接调用没有实际影响（readyz 读的是模块级 `settings` 对象，而该对象是在模块 import 时构造的，reload 后 setenv 也太晚）。去掉 reload 后，所有测试仍应正常工作。

### Step 1.1: 先验证"不 reload"假设

- [ ] **读取当前失败状态**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest tests/unit/ -p no:cacheprovider 2>&1 | tail -5`
Expected: `1 failed, 116 passed, 2 skipped`（当前的失败状态）

### Step 1.2: 修改 test_health_endpoints.py

- [ ] **替换整个文件内容**

覆写 `backend/tests/unit/test_health_endpoints.py`：

```python
import pytest

import app.main as main_module


class _FakeSession:
    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def execute(self, _stmt) -> None:
        if self.should_fail:
            raise RuntimeError("db down")


class _FakeSessionContext:
    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def __aenter__(self) -> _FakeSession:
        return _FakeSession(self.should_fail)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_readyz_returns_ok_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(False),
    )

    async def fake_background_ready():
        return True, {"worker": True, "reaper": True, "scheduler": True}

    monkeypatch.setattr(main_module, "_background_ready", fake_background_ready)

    response = await main_module.readyz()

    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'


@pytest.mark.asyncio
async def test_readyz_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(True),
    )

    response = await main_module.readyz()

    assert response.status_code == 503
    assert response.body == b'{"status":"error","reason":"database_unavailable"}'


@pytest.mark.asyncio
async def test_readyz_returns_503_when_background_service_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(False),
    )

    async def fake_background_ready():
        return False, {"worker": True, "reaper": False, "scheduler": True}

    monkeypatch.setattr(main_module, "_background_ready", fake_background_ready)

    response = await main_module.readyz()

    assert response.status_code == 503
    assert b'"reason":"background_services_unavailable"' in response.body


@pytest.mark.asyncio
async def test_readyz_allows_disabled_background_roles(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(False),
    )
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            process_enable_worker=False,
            process_enable_reaper=False,
            process_enable_scheduler=False,
        ),
    )

    response = await main_module.readyz()

    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'
```

**变更说明：**
- 删掉了所有 `import importlib` 和 `importlib.reload(main_module)` 调用
- 删掉了所有 `monkeypatch.setenv("APP_ENV", "development")`（对 readyz 直接调用无效）
- `import app.main as main_module` 移到文件顶部（import 一次就够）
- 每个测试仍然通过 `monkeypatch.setattr` 覆写模块级属性，这是正确且干净的 mock 方式

### Step 1.3: 单独运行 test_health_endpoints.py 验证它还能通过

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest tests/unit/test_health_endpoints.py -v -p no:cacheprovider 2>&1 | tail -15`
Expected: `4 passed`

### Step 1.4: 运行全量测试验证污染已消除

- [ ] **全量运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest -p no:cacheprovider 2>&1 | tail -5`
Expected: `117 passed, 2 skipped`（原 116 passed + 被修复的 1 个 = 117）

### Step 1.5: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/tests/unit/test_health_endpoints.py
git commit -m "fix(test): remove importlib.reload to stop class identity pollution"
```

---

### Task 2: 修复 Alembic 两个 migration heads

**Files:**
- Modify: `backend/alembic/versions/20260410_1300_extend_zipcode_rule_operator.py`

**Problem (已验证):**
- `20260410_0001_archive_uq_and_cleanup.py` revises `20260409_1710`
- `20260410_0002_add_calc_enabled.py` revises `20260410_0001`
- `20260410_1300_extend_zipcode_rule_operator.py` revises `20260409_1710` ← 跳过了 0001/0002 链条！

这导致存在两个 head：`20260410_0002` 和 `20260410_1300`。`alembic upgrade head` 会失败，部署不可用。

**修复策略:** 把 `20260410_1300` 的 `down_revision` 改为指向 `20260410_0002`，让 migration 形成线性链：`1710 → 0001 → 0002 → 1300`。

这是**时间上合理**的变更（`1300` 时间戳晚于 `0002`），并且两个 migration 内容独立（`calc_enabled` 加字段 vs. `zipcode_rule` 扩展枚举），重排顺序不会引入冲突。

### Step 2.1: 修改 down_revision

- [ ] **编辑 `backend/alembic/versions/20260410_1300_extend_zipcode_rule_operator.py`**

将第 13 行：
```python
down_revision: str | Sequence[str] | None = "20260409_1710"
```

改为：
```python
down_revision: str | Sequence[str] | None = "20260410_0002"
```

### Step 2.2: 验证只有一个 head

- [ ] **运行 alembic heads**

Run: `cd E:/Ai_project/restock_system/backend && alembic heads 2>&1`
Expected: 只输出一行，即 `20260410_1300 (head)`

如果环境没有配置好 alembic（缺少 DATABASE_URL）也没关系，能拿到 heads 输出就够了。如果命令失败，改用 Python 方式：

Run: `cd E:/Ai_project/restock_system/backend && python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
config = Config('alembic.ini')
script = ScriptDirectory.from_config(config)
heads = script.get_heads()
print('heads:', heads)
assert len(heads) == 1, f'expected 1 head, got {len(heads)}: {heads}'
print('OK: single head')
"`
Expected: `OK: single head`

### Step 2.3: 验证链条完整

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
config = Config('alembic.ini')
script = ScriptDirectory.from_config(config)
revisions = list(script.walk_revisions())
print('revision count:', len(revisions))
for rev in reversed(revisions):
    print(f'  {rev.revision} <- {rev.down_revision}')
"`
Expected: 7 revisions，链条连续：`20260408_1500 <- None`、`20260410_1300 <- 20260410_0002` 等。

### Step 2.4: 确认 backend 测试仍然全绿

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest -p no:cacheprovider 2>&1 | tail -3`
Expected: `117 passed, 2 skipped`

### Step 2.5: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/alembic/versions/20260410_1300_extend_zipcode_rule_operator.py
git commit -m "fix(alembic): chain zipcode_rule operator migration after calc_enabled"
```

---

## Part β: 补业务核心测试

### Task 3: engine/runner.py 核心路径测试

**Files:**
- Create: `backend/tests/unit/test_engine_runner.py`

**Why:** `engine/runner.py` 是补货计算的总编排器，负责执行 6 个 step 并把结果写入 `suggestion` 表。当前覆盖率 **24%**。这里出 bug 意味着所有补货建议都算错。

**Strategy:** 用 `_FakeDb` 和 mock 函数隔离 `run_engine` 的编排逻辑。不测数学细节（各 step 自己有测试），只测 run_engine 的几个关键路径：
- 没启用 SKU 时返回 None
- 有 SKU 时归档旧建议 + 生成新 suggestion
- `total_qty <= 0` 的 SKU 被跳过
- 缺 `commodity_id` 的 SKU 被标记 `push_blocker="missing_commodity_id"`

### Step 3.1: 先读取 runner.py 了解签名和依赖

- [ ] **读取 runner.py 的 run_engine 签名**

Run: `cd E:/Ai_project/restock_system/backend && sed -n '1,120p' app/engine/runner.py`

记录：
- `run_engine` 的参数签名
- 它依赖的外部函数（比如 `run_step1`, `_archive_active`, `_persist_suggestion`, `load_local_inventory` 等）
- 它返回什么

**重要**: 真实代码的细节可能和预期不同。以实际读到的代码为准。如果 `run_engine` 的签名或依赖与下面预估的不同，请调整下面的测试 mock 路径。

### Step 3.2: 创建测试文件

- [ ] **创建 `backend/tests/unit/test_engine_runner.py`**

```python
"""Tests for the main engine orchestrator run_engine.

These tests verify the orchestration logic (which steps are called,
how results are aggregated) without exercising the math of individual
steps (each step module has its own tests).
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.runner import run_engine


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> "_ScalarsProxy":
        return _ScalarsProxy(self._value)

    def all(self) -> list[Any]:
        return list(self._value) if isinstance(self._value, list) else [self._value]


class _ScalarsProxy:
    def __init__(self, values: Any) -> None:
        self._values = values if isinstance(values, list) else [values]

    def all(self) -> list[Any]:
        return list(self._values)


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.commits = 0
        self.added_objs: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        if self._responses:
            return self._responses.pop(0)
        return _ScalarResult(None)

    def add(self, obj: Any) -> None:
        self.added_objs.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added_objs.extend(objs)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass
```

### Step 3.3: 运行空文件确认 import + 基础结构 OK

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest tests/unit/test_engine_runner.py -p no:cacheprovider 2>&1 | tail -5`
Expected: `no tests ran` 或类似——说明 import 没报错

### Step 3.4: 根据 Step 3.1 读到的实际 run_engine 代码，针对性写 1 个最简单的测试

**基于 Step 3.1 读到的真实代码**，追加一个简单测试到 `test_engine_runner.py` 末尾。

由于 `run_engine` 是 150+ 行的复杂编排器，测试必须 mock 它调用的每个 step 函数。具体 mock 哪些函数取决于 Step 3.1 的观察。

**最小化测试模板** — 只验证"没启用 SKU 时什么都不做"：

```python
@pytest.mark.asyncio
async def test_run_engine_returns_none_when_no_enabled_skus() -> None:
    """If no SKUs are enabled, run_engine should skip all step execution."""
    # Mock the DB to return an empty SKU list when queried
    # (Actual query path depends on runner.py implementation — adjust as needed)
    db = _FakeDb(
        [
            _ScalarResult([]),  # empty enabled SKUs
        ]
    )

    # Mock the settings and global config load
    mock_config = SimpleNamespace(
        default_buffer_days=30,
        default_target_days=60,
        default_lead_time_days=50,
        default_purchase_warehouse_id="WH-001",
        include_tax="0",
        default_calc_cron="0 8 * * *",
    )

    # Depending on runner.py, you may need to patch more — add patches until the test
    # either passes or fails with an assertion rather than an import error
    with patch("app.engine.runner.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        # If run_engine requires a config argument or reads it from DB, adjust accordingly
        # Example: result = await run_engine()
        # result = await run_engine(triggered_by="test")
        # assert result is None or result.total_items == 0
        pass  # placeholder — replace with actual call once signature is known
```

**注意：** 这个测试是占位符。**实际写的时候必须先看 runner.py 的真实签名和 DB 查询路径**，然后把 placeholder 替换成真正的测试。

**如果 Step 3.1 显示 run_engine 太复杂难以 mock（>10 个依赖），改变策略：**
- 跳过 run_engine 的单元测试
- 改为 `_archive_active` 和 `_persist_suggestion` 等内部辅助函数的测试
- 在注释中说明"run_engine 需要集成测试，已留作后续工作"

### Step 3.5: 运行新增测试

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest tests/unit/test_engine_runner.py -v -p no:cacheprovider 2>&1 | tail -15`
Expected: 至少 1 个测试 pass

### Step 3.6: 检查覆盖率提升

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest --cov=app.engine.runner --cov-report=term-missing -p no:cacheprovider tests/unit/test_engine_runner.py tests/unit/test_engine_step1.py tests/unit/test_engine_step2.py tests/unit/test_engine_step3.py tests/unit/test_engine_step4.py tests/unit/test_engine_step5.py tests/unit/test_engine_step6.py 2>&1 | tail -10`
Expected: `app/engine/runner.py` 覆盖率提升（即使只升 5-10 个百分点也比 24% 强）

### Step 3.7: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/tests/unit/test_engine_runner.py
git commit -m "test(engine): add unit tests for run_engine orchestrator"
```

---

### Task 4: core/security.py 测试

**Files:**
- Create: `backend/tests/unit/test_security.py`

**Why:** `core/security.py` 是全部认证路径的基石（密码 hash + JWT 编解码）。当前覆盖率 **42%**，缺 `hash_password`、`verify_password`、`decode_token` 的完整测试。

### Step 4.1: 创建测试文件

- [ ] **创建 `backend/tests/unit/test_security.py`**

```python
"""Unit tests for app.core.security."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from app.core.exceptions import Unauthorized
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_bcrypt_hash() -> None:
    hashed = hash_password("correct horse")
    # bcrypt hashes start with $2b$ (or $2a$/$2y$)
    assert hashed.startswith("$2")
    # and are 60 chars long
    assert len(hashed) == 60


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("battery staple", hashed) is False


def test_hash_password_is_salted_unique() -> None:
    """Same plaintext should produce different hashes (bcrypt salts)."""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    # But both should still verify
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_create_access_token_contains_expected_claims() -> None:
    token = create_access_token(subject="owner")
    # Decode without verification to inspect payload
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["sub"] == "owner"
    assert "iat" in payload
    assert "exp" in payload
    # exp should be in the future
    assert payload["exp"] > payload["iat"]


def test_create_access_token_includes_extra_claims() -> None:
    token = create_access_token(subject="owner", extra={"role": "admin"})
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["role"] == "admin"
    assert payload["sub"] == "owner"


def test_decode_token_returns_payload_on_valid_token() -> None:
    token = create_access_token(subject="owner")
    payload = decode_token(token)
    assert payload["sub"] == "owner"


def test_decode_token_rejects_invalid_signature() -> None:
    from app.config import get_settings

    # Forge a token signed with a wrong secret
    bad_token = jwt.encode(
        {"sub": "owner", "iat": int(datetime.now(UTC).timestamp())},
        "wrong_secret",
        algorithm=get_settings().jwt_algorithm,
    )
    with pytest.raises(Unauthorized):
        decode_token(bad_token)


def test_decode_token_rejects_expired_token() -> None:
    from app.config import get_settings

    settings = get_settings()
    # Sign a token with exp in the past
    past = datetime.now(UTC) - timedelta(hours=1)
    expired_token = jwt.encode(
        {
            "sub": "owner",
            "iat": int((past - timedelta(hours=1)).timestamp()),
            "exp": int(past.timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Unauthorized):
        decode_token(expired_token)


def test_decode_token_rejects_malformed_token() -> None:
    with pytest.raises(Unauthorized):
        decode_token("not.a.valid.jwt")
```

### Step 4.2: 运行测试

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest tests/unit/test_security.py -v -p no:cacheprovider 2>&1 | tail -20`
Expected: 所有 10 个测试 pass

### Step 4.3: 检查覆盖率提升

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest --cov=app.core.security --cov-report=term-missing -p no:cacheprovider tests/unit/test_security.py 2>&1 | tail -5`
Expected: `app/core/security.py` 覆盖率 ≥ 85%

### Step 4.4: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/tests/unit/test_security.py
git commit -m "test(security): add unit tests for password hashing and JWT encode/decode"
```

---

## Part γ: 防御性加强（可选）

### Task 5: conftest.py 加 get_settings cache_clear fixture

**Files:**
- Modify: `backend/tests/conftest.py`

**Why:** Task 1 虽然移除了 `importlib.reload`，但项目里用了 `@lru_cache` 修饰 `get_settings`。未来如果有测试 mock env 变量并期望下一次 `get_settings()` 返回新值，lru_cache 会返回旧的。加一个 autouse fixture 防御性清空缓存。

**注意：** 这不是修 bug，是预防。当前所有测试都不依赖这个，可跳过。

### Step 5.1: 修改 conftest.py

- [ ] **读取当前 conftest.py**

Run: `cd E:/Ai_project/restock_system/backend && cat tests/conftest.py`

- [ ] **在现有内容基础上追加**

在文件末尾追加：

```python
@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Defensively clear get_settings lru_cache before and after each test.

    Prevents pollution from tests that mutate environment variables or patch
    settings attributes in ways that could be cached across tests.
    """
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

如果 `pytest` 已在文件顶部 import，不需要再 import。如果没有，在文件顶部加 `import pytest`。

### Step 5.2: 运行全量测试

- [ ] **运行**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest -p no:cacheprovider 2>&1 | tail -5`
Expected: 所有测试 pass（与 Task 4 后的状态一致）

### Step 5.3: 提交

- [ ] **提交**

```bash
cd E:/Ai_project/restock_system
git add backend/tests/conftest.py
git commit -m "test(conftest): add autouse fixture to clear settings cache between tests"
```

---

## Task 6: 最终全量验证

- [ ] **后端 ruff**

Run: `cd E:/Ai_project/restock_system/backend && python -m ruff check . 2>&1 | tail -3`
Expected: `All checks passed!`

- [ ] **后端 mypy**

Run: `cd E:/Ai_project/restock_system/backend && python -m mypy app 2>&1 | tail -3`
Expected: `Success: no issues found in 87 source files`

- [ ] **后端全量测试 + 覆盖率**

Run: `cd E:/Ai_project/restock_system/backend && python -m pytest --cov --cov-config=.coveragerc --cov-report=term -p no:cacheprovider 2>&1 | tail -5`
Expected:
- 测试数量：117+（Task 3 和 4 各新增测试）全部 pass
- 覆盖率 ≥ 55%
- 关键模块覆盖率提升：`engine/runner.py` > 24%，`core/security.py` > 85%

- [ ] **Alembic 单 head**

Run: `cd E:/Ai_project/restock_system/backend && python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
config = Config('alembic.ini')
script = ScriptDirectory.from_config(config)
heads = script.get_heads()
assert len(heads) == 1, f'FAIL: {len(heads)} heads: {heads}'
print('OK: single head', heads[0])
"`
Expected: `OK: single head <revision>`

- [ ] **前端 lint + type-check + test**

Run: `cd E:/Ai_project/restock_system/frontend && npm run lint && npm run type-check && npm test 2>&1 | tail -5`
Expected: 全部 pass，33 tests passed

- [ ] **git 状态干净**

Run: `cd E:/Ai_project/restock_system && git status --short`
Expected: 无未提交改动

---

## Self-Review

### Spec coverage
- ✅ α1 test_health_endpoints 污染 → Task 1
- ✅ α2 alembic 两个 heads → Task 2
- ✅ α3 JWT 验证 — **验证后无问题**（`jwt.decode` 默认验证 exp + signature），不需要任务，在 Task 4 的 security 测试中会顺带覆盖验证
- ✅ β1 engine/runner 测试 → Task 3
- ✅ β2 core/security 测试 → Task 4
- ✅ γ settings cache fixture → Task 5

### Risk notes
- **Task 1** 是最关键的修复。如果去掉 reload 后 `test_health_endpoints.py` 的某个测试失败，说明该测试确实依赖 reload 行为——那时退回方案是：继续用 reload，但把它放在 xdist 独立进程里运行，或者给它单独 marker 由 CI 独立跑。但根据对代码的分析，不应该发生这种情况。
- **Task 2** 是结构性改动（改 migration 链条）。在生产数据库已经执行过老的顺序的情况下，改 `down_revision` 会让 alembic 认为历史不一致。**因为项目仅 1-5 人内部使用且看起来还在开发阶段**，这个改动可接受。如果线上生产库已有数据跑过 `1300` migration（以旧的 down_revision），需要手工重置 `alembic_version` 表。这一点在 Task 2 commit message 中需要提及。
- **Task 3** 的 runner.py 太复杂，可能写不出完美的单元测试。退化策略是只覆盖 1-2 个最简单的路径，哪怕只把覆盖率从 24% 提到 35% 也是进步。不要强求 60%。
- **Task 5** 是防御性的，可以跳过。

### Type consistency
- `_FakeDb`、`_ScalarResult` 等辅助类在 Task 3 和 4 中保持与 `test_pushback_purchase.py`、`test_warehouse_api.py` 一致的模式
- Task 4 的 JWT 测试使用真实的 `get_settings()`，不 mock —— 依赖 Task 5 或现有的环境配置提供一个默认 secret
