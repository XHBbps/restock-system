# 订单详情失败分类与历史误拉黑清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `sync_order_detail` 将所有 `SaihuAPIError` 当作永久失败的 bug —— 按异常子类分类，瞬时错误（限流 / 网络 / auth 过期）不写 fetch_log 让下轮重试，只有 `SaihuBizError` 才永久拉黑；同时清理历史上被误拉黑的记录。

**Architecture:** 在 `backend/app/sync/order_detail.py` 抽出一个纯函数 `_is_permanent_saihu_error(exc)`，`_fetch_one` 根据它决定是否写 `order_detail_fetch_log`。历史数据通过一次 alembic 数据迁移清理（upgrade 删除瞬时失败行，downgrade 为空 —— 删除不可逆）。

**Tech Stack:** Python 3 / SQLAlchemy / Alembic / pytest（`asyncio_mode = "auto"` 已启用）

**相关背景代码：**
- `backend/app/sync/order_detail.py:34-93` — 待修复的 `sync_order_detail_job` / `_fetch_one`
- `backend/app/sync/order_detail.py:186-202` — 现有 `_log_fetch_failure`（不改，只改调用点）
- `backend/app/core/exceptions.py:65-96` — 异常继承树：`SaihuAPIError` 是基类，`SaihuAuthExpired` / `SaihuRateLimited` / `SaihuBizError` / `SaihuNetworkError` 都继承它
- `backend/app/saihu/client.py:75-97` — tenacity 只对 `SaihuRateLimited` / `SaihuNetworkError` 重试 `saihu_max_retries=3` 次，`SaihuBizError` 不重试 → 到达 `_fetch_one` 时瞬时错误已是"客户端重试耗尽"
- `backend/app/models/order.py:121-133` — `OrderDetailFetchLog` 模型：成功行 `http_status=200, saihu_code=0`；失败行 `http_status=NULL, saihu_code=exc.code`
- `backend/alembic/versions/20260410_1300_extend_zipcode_rule_operator.py` — 最新 revision，用作 down_revision

**分类规则：**

| 异常类 | 是否永久 | 行为 |
|---|---|---|
| `SaihuBizError` | ✅ | 写 `order_detail_fetch_log`（和现在一致）|
| `SaihuRateLimited` | ❌ | 不写日志，下轮重试 |
| `SaihuNetworkError` | ❌ | 不写日志，下轮重试 |
| `SaihuAuthExpired` | ❌ | 不写日志，下轮重试（理论上 client 层已处理，防御性兜底）|
| 裸 `SaihuAPIError` | ❌ | 不写日志（如 client.py:87 `"unreachable"` 兜底）|
| 其他 `Exception` | ❌ | 不写日志（和现在一致）|

---

## Task 1: 抽出分类函数并加单元测试

**Files:**
- Create: `backend/tests/unit/test_sync_order_detail_classification.py`
- Modify: `backend/app/sync/order_detail.py`（新增 `_is_permanent_saihu_error` 函数 + 调整 import）

### Step 1: 写失败的测试

- [ ] Create `backend/tests/unit/test_sync_order_detail_classification.py`:

```python
"""Unit tests for order_detail fetch failure classification.

These tests lock in the rule that only SaihuBizError should be written to
order_detail_fetch_log as a permanent failure. Other Saihu exception subclasses
represent transient issues (client-level tenacity budget exhausted) and must
be allowed to retry on the next sync run.
"""

from app.core.exceptions import (
    SaihuAPIError,
    SaihuAuthExpired,
    SaihuBizError,
    SaihuNetworkError,
    SaihuRateLimited,
)
from app.sync.order_detail import _is_permanent_saihu_error


def test_saihu_biz_error_is_permanent() -> None:
    exc = SaihuBizError("订单不存在", code=40013)
    assert _is_permanent_saihu_error(exc) is True


def test_saihu_rate_limited_is_transient() -> None:
    exc = SaihuRateLimited("被限流", code=40019)
    assert _is_permanent_saihu_error(exc) is False


def test_saihu_network_error_is_transient() -> None:
    exc = SaihuNetworkError("连接超时")
    assert _is_permanent_saihu_error(exc) is False


def test_saihu_auth_expired_is_transient() -> None:
    exc = SaihuAuthExpired("token 失效", code=40001)
    assert _is_permanent_saihu_error(exc) is False


def test_bare_saihu_api_error_is_transient() -> None:
    # client.py raises `SaihuAPIError("unreachable", ...)` as a safety net.
    # Treat unclassified base-class errors as transient so they get another try.
    exc = SaihuAPIError("unreachable")
    assert _is_permanent_saihu_error(exc) is False


def test_generic_exception_is_transient() -> None:
    exc = RuntimeError("boom")
    assert _is_permanent_saihu_error(exc) is False
```

### Step 2: 运行测试确认失败（导入错误）

- [ ] Run:

```bash
cd backend && pytest tests/unit/test_sync_order_detail_classification.py -v
```

Expected: **ImportError** — `_is_permanent_saihu_error` cannot be imported from `app.sync.order_detail`。

### Step 3: 在 `order_detail.py` 中添加分类函数

- [ ] In `backend/app/sync/order_detail.py`, update the import line `from app.core.exceptions import SaihuAPIError` to:

```python
from app.core.exceptions import SaihuAPIError, SaihuBizError
```

- [ ] Append a new module-level function directly above the `@register(JOB_NAME)` decorator (after the existing constants `CONCURRENCY = 3`):

```python
def _is_permanent_saihu_error(exc: BaseException) -> bool:
    """Classify whether ``exc`` should be recorded as a permanent fetch failure.

    Only :class:`SaihuBizError` represents real business-level errors (invalid
    order id, closed shop, malformed response, etc.) that will never succeed
    on retry. Rate-limited / network / auth-expired errors bubble up only
    after the client-level tenacity budget is exhausted but a later run may
    still succeed, so they must NOT be written to ``order_detail_fetch_log``.
    Any other exception type is also treated as transient and left for the
    next run (matches historical behavior for non-Saihu errors).
    """
    return isinstance(exc, SaihuBizError)
```

### Step 4: 运行测试确认通过

- [ ] Run:

```bash
cd backend && pytest tests/unit/test_sync_order_detail_classification.py -v
```

Expected: **6 passed** —— all classification tests green.

### Step 5: Commit

- [ ] Run:

```bash
git add backend/app/sync/order_detail.py backend/tests/unit/test_sync_order_detail_classification.py
git commit -m "test(order_detail): add failure classification helper and unit tests"
```

---

## Task 2: `_fetch_one` 使用分类函数，瞬时错误不写日志

**Files:**
- Modify: `backend/app/sync/order_detail.py:46-65`（`_fetch_one` 的 except 分支）

### Step 1: 改写 `_fetch_one` 的异常分支

- [ ] In `backend/app/sync/order_detail.py`, replace the entire `_fetch_one` function (currently at lines 46-65) with:

```python
    async def _fetch_one(shop_id: str, amazon_order_id: str) -> bool:
        async with sem:
            try:
                detail = await get_order_detail(shop_id=shop_id, amazon_order_id=amazon_order_id)
                async with async_session_factory() as db:
                    await _save_detail(db, shop_id, amazon_order_id, detail)
                    await db.commit()
                return True
            except Exception as exc:
                if _is_permanent_saihu_error(exc):
                    # Only SaihuBizError reaches here — record as permanent so
                    # _find_pending_orders will skip this order on future runs.
                    assert isinstance(exc, SaihuBizError)  # for type narrowing
                    async with async_session_factory() as db:
                        await _log_fetch_failure(db, shop_id, amazon_order_id, exc)
                        await db.commit()
                    logger.warning(
                        "order_detail_fetch_permanent_failure",
                        shop_id=shop_id,
                        amazon_order_id=amazon_order_id,
                        saihu_code=exc.code,
                        error=str(exc),
                    )
                else:
                    # Transient: rate limited, network, auth expired, or
                    # non-Saihu exception. Don't persist — next sync run
                    # will pick this order up again.
                    logger.warning(
                        "order_detail_fetch_transient_failure",
                        shop_id=shop_id,
                        amazon_order_id=amazon_order_id,
                        error=str(exc),
                    )
                return False
```

Note: `_log_fetch_failure` is typed to accept `SaihuAPIError`; `SaihuBizError` is a subclass so the call is already type-correct. The `assert isinstance` exists purely to narrow the type for static analysis.

### Step 2: 修正 `_log_fetch_failure` 的类型注解（可选收紧）

- [ ] In `backend/app/sync/order_detail.py`, update the `_log_fetch_failure` signature (currently line 186-191) — change the `exc` parameter type from `SaihuAPIError` to `SaihuBizError`, because after the classification change this function is only ever called with a biz error:

```python
async def _log_fetch_failure(
    db: AsyncSession,
    shop_id: str,
    amazon_order_id: str,
    exc: SaihuBizError,
) -> None:
```

### Step 3: 运行现有相关测试确认不回归

- [ ] Run:

```bash
cd backend && pytest tests/unit/test_sync_order_detail_classification.py tests/unit/test_sync_all.py tests/unit/test_data_order_detail_visibility.py -v
```

Expected: **all pass**（分类测试 6 个 + sync_all 步骤顺序 + order_detail 可见性）

### Step 4: 全量跑后端 pytest 避免更大回归

- [ ] Run:

```bash
cd backend && pytest
```

Expected: **all pass**（如有预先失败项，记录并确认与本次改动无关）

### Step 5: Commit

- [ ] Run:

```bash
git add backend/app/sync/order_detail.py
git commit -m "fix(sync): only treat SaihuBizError as permanent order_detail failure

Previously any SaihuAPIError subclass caused an order to be written to
order_detail_fetch_log, permanently blocking retries. But SaihuRateLimited,
SaihuNetworkError and SaihuAuthExpired are transient — they bubble up only
after the client-level tenacity budget is exhausted and the next sync run
may succeed. Only SaihuBizError represents a true permanent failure."
```

---

## Task 3: 数据迁移 —— 清理历史误拉黑记录

**Files:**
- Create: `backend/alembic/versions/20260411_1000_cleanup_transient_order_detail_fetch_log.py`

### Step 1: 确认当前最新 revision

- [ ] Run:

```bash
cd backend && alembic heads
```

Expected: single head **`20260410_1300`**（对应 `20260410_1300_extend_zipcode_rule_operator.py`）。如果显示的 head 不同，用实际返回的 revision 作为下一步的 `down_revision`。

### Step 2: 创建数据迁移文件

- [ ] Create `backend/alembic/versions/20260411_1000_cleanup_transient_order_detail_fetch_log.py`:

```python
"""Cleanup transient failures from order_detail_fetch_log.

Revision ID: 20260411_1000
Revises: 20260410_1300
Create Date: 2026-04-11

Background
----------
Before 2026-04-11 ``sync_order_detail`` treated every ``SaihuAPIError``
subclass as a permanent failure and wrote it to ``order_detail_fetch_log``,
which prevented future retries for the same order. In reality only
``SaihuBizError`` is permanent — ``SaihuRateLimited`` / ``SaihuAuthExpired``
/ ``SaihuNetworkError`` only surface after the client-level tenacity retry
budget is exhausted and a subsequent run could succeed.

This data-only migration deletes the mis-classified rows so the next
``sync_order_detail`` run can retry them.

Deletion predicate
------------------
- ``http_status IS NULL``: distinguishes failure rows from success rows,
  which are written with ``http_status = 200``.
- ``saihu_code IS NULL OR saihu_code IN (40001, 40019)``:
    - ``40019`` → SaihuRateLimited
    - ``40001`` → SaihuAuthExpired
    - ``NULL``  → SaihuNetworkError / bare SaihuAPIError (no business code)

Rows with any other non-zero ``saihu_code`` represent real business errors
(invalid order id, closed shop, etc.) and are preserved.

Downgrade cannot restore deleted rows; it is a no-op. Re-running
``sync_order_detail`` will re-populate ``order_detail_fetch_log`` with any
orders that still legitimately fail.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260411_1000"
down_revision: str | Sequence[str] | None = "20260410_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM order_detail_fetch_log
         WHERE http_status IS NULL
           AND (saihu_code IS NULL OR saihu_code IN (40001, 40019))
        """
    )


def downgrade() -> None:
    # Data-only migration; deleted rows cannot be restored.
    pass
```

### Step 3: 本地 dry-run 验证迁移脚本语法

- [ ] Run:

```bash
cd backend && alembic upgrade head --sql
```

Expected: 输出 SQL 包含我们刚写的 `DELETE FROM order_detail_fetch_log ...` 语句，无 Python 错误。**这一步只打印 SQL，不执行，是纯语法 + 依赖链检查。**

### Step 4: 在本地/dev 环境实际执行迁移（如果可用）

- [ ] Run (仅在本地/dev 数据库):

```bash
cd backend && alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade 20260410_1300 -> 20260411_1000, Cleanup transient failures from order_detail_fetch_log` — no errors。

> 如果当前环境没有可用的 dev 数据库，跳过这一步 —— 迁移会在下一次部署时自动运行。在 PR 描述里标注"数据迁移未本地执行"并让部署负责人注意。

### Step 5: Commit

- [ ] Run:

```bash
git add backend/alembic/versions/20260411_1000_cleanup_transient_order_detail_fetch_log.py
git commit -m "chore(alembic): cleanup transient failures from order_detail_fetch_log

Removes rows mis-classified as permanent failures before the sync_order_detail
exception classification fix. Predicate:
  http_status IS NULL AND (saihu_code IS NULL OR saihu_code IN (40001, 40019))
Preserves real SaihuBizError rows for permanent failures."
```

---

## Task 4: 文档同步

**Files:**
- Modify: `docs/PROGRESS.md`（"最近更新" 追加一条）

### Step 1: 查看现有 PROGRESS.md 格式

- [ ] Read `docs/PROGRESS.md` to see the "最近更新" section format — locate the most recent entry and match its date / bullet style。

### Step 2: 追加一条更新

- [ ] 在 `docs/PROGRESS.md` "最近更新" 块的顶部追加（用仓库已有的日期前缀风格，本条日期 `2026-04-11`）：

```markdown
- 2026-04-11 fix(sync): `sync_order_detail` 按异常子类分类失败 —— 仅 `SaihuBizError` 写入 `order_detail_fetch_log` 作为永久失败，限流 / 网络 / auth 过期由下轮调度自动重试；附带 alembic 数据迁移 `20260411_1000` 清理历史误拉黑记录。
```

> 如果 `docs/PROGRESS.md` 的现有条目用的是别的 bullet 风格（例如 `### 2026-04-11` 标题块），按现有格式调整 —— 不要机械照搬上面的字符串。

### Step 3: Commit

- [ ] Run:

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): note order_detail fetch retry classification fix"
```

---

## Task 5: 收尾自检

### Step 1: 再次全量跑 pytest，验证整条链仍绿

- [ ] Run:

```bash
cd backend && pytest
```

Expected: **all pass**。如有新增失败，必须回到相关 Task 修正（不允许带失败提交 PR）。

### Step 2: Git log 自检

- [ ] Run:

```bash
git log --oneline -n 6
```

Expected: 看到 4 条新 commit（Task 1 / 2 / 3 / 4），顺序从新到旧：

```
<hash> docs(progress): note order_detail fetch retry classification fix
<hash> chore(alembic): cleanup transient failures from order_detail_fetch_log
<hash> fix(sync): only treat SaihuBizError as permanent order_detail failure
<hash> test(order_detail): add failure classification helper and unit tests
```

### Step 3: 检查工作区干净

- [ ] Run:

```bash
git status
```

Expected: `nothing to commit, working tree clean`（或仅剩本 plan 文档本身未 commit —— 如是，追加一条 `docs(plans): ...` commit）

---

## Out of Scope（本次不做）

为保证改动最小、可快速验证，以下事项**刻意排除**：

- **吞吐量 B 方向**：调整 `MAX_PER_RUN` / `CONCURRENCY` / 独立调度周期 —— A 修完后积压会自动被下轮重试消化，先观察再决定是否需要进一步调优。
- **按 `saihu_code` 精细区分永久性**：当前 `SaihuBizError` 内部不同业务码（40013/40011/...）是否都该永久拉黑，取决于业务含义 —— 可基于生产日志后续再收敛白/黑名单。
- **手动重拉某条订单的 API**：现有 `_find_pending_orders` 纯靠 fetch_log 过滤，没有"force retry"通道。如果业务上有需要，可后续再加。
- **基础 SaihuAPIError 是否写日志**：目前分类函数将裸 `SaihuAPIError`（如 client 的 `unreachable` 兜底）视为瞬时。这在数量级上极少发生，不值得增加分支。
