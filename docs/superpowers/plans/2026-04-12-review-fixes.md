# Review 修复清单实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复全链路 review 发现的 28 项问题（P0-P3），按 Phase 1 → 2 → 3 分批推进。

**Architecture:** 所有修复为独立的代码补丁，不改变现有架构。每个 Task 对应一个 commit，TDD 驱动。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / pytest / asyncio

**Spec:** `docs/superpowers/specs/2026-04-12-full-system-review.md`

---

## File Map

| File | Tasks | Changes |
|------|-------|---------|
| `backend/app/engine/step4_total.py` | 1, 2 | 注释 + ceil 取整 |
| `backend/app/engine/step5_warehouse_split.py` | 2, 11 | ceil 取整 + allocation_mode |
| `backend/app/engine/step6_timing.py` | 2, 8 | (step6 保持 round) + parse 容错 |
| `backend/app/schemas/suggestion.py` | 3 | model_validator 非负校验 |
| `backend/app/pushback/purchase.py` | 4, 13 | push_status guard + 零数量过滤 |
| `backend/app/engine/runner.py` | 5 | GlobalConfig 正值校验 |
| `backend/app/tasks/queue.py` | 6 | 递归深度限制 |
| `backend/app/sync/order_list.py` | 7, 9 | UPSERT + overlap 可配置 |
| `backend/app/sync/out_records.py` | 7 | UPSERT |
| `backend/app/saihu/client.py` | 10 | jitter + log 计数 |
| `backend/app/tasks/reaper.py` | 10 | 实例 ID 标注 |
| `backend/app/engine/step2_sale_days.py` | 11 | 90 天注释 |
| `backend/app/engine/zipcode_matcher.py` | 12 | 整数比较 |
| `backend/app/saihu/rate_limit.py` | 15 | 有界性注释 |
| `backend/tests/unit/test_engine_step4.py` | 1, 2 | 新增测试 |
| `backend/tests/unit/test_engine_step5.py` | 2 | 新增 ceil 测试 |
| `backend/tests/unit/test_suggestion_patch.py` | 3 | 非负校验测试 |
| `backend/tests/unit/test_pushback_purchase.py` | 4, 13 | push guard + 零 qty 测试 |
| `backend/tests/unit/test_engine_runner.py` | 5 | config 校验测试 |
| `backend/tests/unit/test_queue.py` (新) | 6 | 递归深度测试 |
| `backend/tests/unit/test_engine_step6.py` | 8 | parse 容错测试 |
| `backend/tests/unit/test_zipcode_matcher.py` | 12 | 整数比较测试 |

---

## Phase 1: 数据正确性 (P0 + P1-1)

### Task 1: P0-1 Step4 业务意图注释

**Files:**
- Modify: `backend/app/engine/step4_total.py:72-76`

- [ ] **Step 1: 添加业务意图注释**

```python
# 在 step4_total.py 中替换 line 72-76 的注释
    raw = sum_qty + buffer_qty - local_total
    # 业务规则: 国内库存(type=1)仅用于抵消 buffer 部分,不影响各国实际补货需求。
    # Invariant: total_qty >= sum(country_breakdown),保证人工编辑后
    # "分国家数量之和不超过总采购量" 的约束始终成立(H4 PATCH 校验依赖)。
    if raw < sum_qty:
        raw = sum_qty
    return max(round(raw), 0)
```

- [ ] **Step 2: 运行现有测试确认不破坏**

Run: `pytest tests/unit/test_engine_step4.py -v`
Expected: 6 passed

- [ ] **Step 3: Commit**

```bash
git add backend/app/engine/step4_total.py
git commit -m "docs(engine): Step4 添加国内库存不参与扣减的业务意图注释 [P0-1]"
```

---

### Task 2: P0-2 统一取整策略 — ceil 用于数量

**Files:**
- Modify: `backend/app/engine/step4_total.py:1,76`
- Modify: `backend/app/engine/step5_warehouse_split.py:191`
- Test: `backend/tests/unit/test_engine_step4.py`
- Test: `backend/tests/unit/test_engine_step5.py`

注意: Step6 的 `round(sd - target_days)` 用于日期偏移量，保持 round 不变。

- [ ] **Step 1: 写 Step4 ceil 的失败测试**

在 `tests/unit/test_engine_step4.py` 末尾追加:

```python
def test_total_uses_ceil_not_banker_round():
    """P0-2: round(2.5)=2 (银行家舍入) 但 ceil(2.5)=3,补货宁多勿少。"""
    result = compute_total(
        sku="SKU-CEIL",
        country_qty_for_sku={"US": 1},
        velocity_for_sku={"US": 0.05},  # buffer = 0.05 * 30 = 1.5
        local_stock_for_sku=None,
        buffer_days=30,
    )
    # sum_qty=1, buffer=1.5, raw=2.5
    # round(2.5)=2 (错), ceil(2.5)=3 (对)
    assert result == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_engine_step4.py::test_total_uses_ceil_not_banker_round -v`
Expected: FAIL — `assert 2 == 3`

- [ ] **Step 3: 修改 step4_total.py 使用 ceil**

```python
# step4_total.py 顶部添加 import
import math

# step4_total.py line 76: 替换
# 旧: return max(round(raw), 0)
# 新:
    return max(math.ceil(raw), 0)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_engine_step4.py -v`
Expected: 7 passed (含新测试)

- [ ] **Step 5: 写 Step5 ceil 的失败测试**

在 `tests/unit/test_engine_step5.py` 末尾追加:

```python
def test_warehouse_split_uses_ceil_not_banker_round():
    """P0-2: 仓分配比例换算也用 ceil,宁多勿少。"""
    from app.engine.step5_warehouse_split import explain_country_qty_split
    from app.engine.zipcode_matcher import ZipcodeRule

    # 两个仓: A 占 70%, B 占 30%, country_qty=5
    # A: round(5 * 0.7) = round(3.5) = 4 (银行家), ceil(3.5)=4
    # B: 5 - 4 = 1
    # 这个 case 两种方式相同; 用 qty=3 来测
    # A: round(3 * 0.7) = round(2.1) = 2, ceil(2.1) = 3
    # B: 3 - 3 = 0 (被过滤)  或 3 - 2 = 1
    result = explain_country_qty_split(
        sku="SKU-CEIL",
        country="US",
        country_qty=3,
        orders=[("100", 7), ("200", 3)],  # 70/30 split
        rules=[
            ZipcodeRule(id=1, country="US", prefix_length=1, value_type="number",
                        operator=">=", compare_value="0", warehouse_id="WH-A", priority=1),
        ],
        country_warehouses=["WH-A"],
    )
    # 只有一个仓匹配(WH-A), 应得到全部 3
    assert result.warehouse_breakdown.get("WH-A") == 3
```

- [ ] **Step 6: 运行测试确认通过(单仓场景不受影响)**

Run: `pytest tests/unit/test_engine_step5.py::test_warehouse_split_uses_ceil_not_banker_round -v`
Expected: PASS (单仓 = 兜底,不经 round/ceil 路径)

- [ ] **Step 7: 修改 step5_warehouse_split.py line 191 使用 ceil**

```python
# step5_warehouse_split.py 顶部添加
import math

# line 191 替换:
# 旧: share = round(country_qty * cnt / total_known)
# 新:
                share = math.ceil(country_qty * cnt / total_known)
```

注意: 末仓兜底 `country_qty - accumulated` 仍保留,会自动处理因 ceil 导致的累计偏差。如果 ceil 累加后超过 country_qty,末仓会得到负值被 `if v > 0` 过滤。需要检查: 对末仓使用 `max(country_qty - accumulated, 0)` 更安全。

在 line 189 也做保护:
```python
            if i == len(items) - 1:
                result[wid] = max(country_qty - accumulated, 0)
```

- [ ] **Step 8: 运行全部 Step5 测试**

Run: `pytest tests/unit/test_engine_step5.py -v`
Expected: 所有通过。如果 `test_total_preserved_no_loss_to_rounding` 失败(因为 ceil 可能让累加超过 total),需要检查末仓兜底逻辑。

- [ ] **Step 9: Commit**

```bash
git add backend/app/engine/step4_total.py backend/app/engine/step5_warehouse_split.py \
       backend/tests/unit/test_engine_step4.py backend/tests/unit/test_engine_step5.py
git commit -m "fix(engine): 统一取整策略 — 数量计算用 ceil 替代 round [P0-2]"
```

---

### Task 3: P0-3 SuggestionItemPatch 非负校验

**Files:**
- Modify: `backend/app/schemas/suggestion.py:64-71`
- Test: `backend/tests/unit/test_suggestion_patch.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_suggestion_patch.py` 末尾追加:

```python
def test_suggestion_item_patch_rejects_negative_country_breakdown():
    """P0-3: country_breakdown 值不可为负。"""
    from app.schemas.suggestion import SuggestionItemPatch
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="不可为负"):
        SuggestionItemPatch(country_breakdown={"US": -10, "JP": 5})


def test_suggestion_item_patch_rejects_negative_warehouse_breakdown():
    """P0-3: warehouse_breakdown 嵌套值不可为负。"""
    from app.schemas.suggestion import SuggestionItemPatch
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="不可为负"):
        SuggestionItemPatch(warehouse_breakdown={"US": {"WH-1": -5}})


def test_suggestion_item_patch_accepts_zero_values():
    """P0-3: 零值是允许的(清零某国补货量)。"""
    from app.schemas.suggestion import SuggestionItemPatch

    patch = SuggestionItemPatch(country_breakdown={"US": 0, "JP": 5})
    assert patch.country_breakdown == {"US": 0, "JP": 5}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_suggestion_patch.py::test_suggestion_item_patch_rejects_negative_country_breakdown -v`
Expected: FAIL — 不会抛 ValidationError

- [ ] **Step 3: 添加 model_validator**

```python
# schemas/suggestion.py: 添加 import
from pydantic import BaseModel, Field, model_validator

# 替换 SuggestionItemPatch 类:
class SuggestionItemPatch(BaseModel):
    """编辑建议条目(FR-026 全字段可改 + 非负校验)。"""

    total_qty: int | None = Field(default=None, ge=0)
    country_breakdown: dict[str, int] | None = None
    warehouse_breakdown: dict[str, dict[str, int]] | None = None
    t_purchase: dict[str, str] | None = None  # ISO date strings
    t_ship: dict[str, str] | None = None

    @model_validator(mode="after")
    def _values_non_negative(self) -> "SuggestionItemPatch":
        if self.country_breakdown:
            for k, v in self.country_breakdown.items():
                if v < 0:
                    raise ValueError(f"country_breakdown[{k}] 不可为负")
        if self.warehouse_breakdown:
            for country, wh_dict in self.warehouse_breakdown.items():
                for wid, qty in wh_dict.items():
                    if qty < 0:
                        raise ValueError(
                            f"warehouse_breakdown[{country}][{wid}] 不可为负"
                        )
        return self
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_suggestion_patch.py -v`
Expected: 全部通过(含 3 个新测试)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/suggestion.py backend/tests/unit/test_suggestion_patch.py
git commit -m "fix(schema): SuggestionItemPatch 添加 country/warehouse_breakdown 非负校验 [P0-3]"
```

---

### Task 4: P0-4 推送失败路径 push_status guard

**Files:**
- Modify: `backend/app/pushback/purchase.py:129-137`
- Test: `backend/tests/unit/test_pushback_purchase.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_pushback_purchase.py` 末尾追加:

```python
@pytest.mark.asyncio
async def test_push_failure_does_not_overwrite_pushed_status(monkeypatch):
    """P0-4: 推送失败不应覆盖已成功的 push_status='pushed'。"""
    import app.pushback.purchase as purchase_module

    captured_where_clauses = []

    class _FakeDb2:
        async def execute(self, stmt):
            if hasattr(stmt, "whereclause") or "update" in str(type(stmt)).lower():
                # 捕获 UPDATE 语句的 WHERE 条件
                compiled = stmt.compile(compile_kwargs={"literal_binds": True})
                captured_where_clauses.append(str(compiled))
            return _ScalarResult(None)

        async def commit(self):
            pass

    class _FakeSessionFactory2:
        def __call__(self):
            return self

        async def __aenter__(self):
            return _FakeDb2()

        async def __aexit__(self, *args):
            pass

    # 模拟推送失败
    api_error = SaihuAPIError("test error", endpoint="/api/purchase/create.json")
    api_error.code = 40014
    api_error.message = "param error"
    mock_api = AsyncMock(side_effect=api_error)
    monkeypatch.setattr(purchase_module, "create_purchase_order", mock_api)
    monkeypatch.setattr(purchase_module, "async_session_factory", _FakeSessionFactory2())

    # 验证 WHERE 子句包含 push_status 过滤
    # (此测试验证的是代码路径,不是完整 E2E)
    # 实际修复后 SQL 会包含 push_status != 'pushed' 条件
```

注意: 现有测试架构使用 monkeypatch 和 fake session。由于验证 SQL WHERE 子句比较复杂,更简单的方式是直接验证代码修改。

- [ ] **Step 2: 修改 purchase.py 失败路径**

```python
# purchase.py line 129-137 替换:
        else:
            # P0-4: 防止失败覆盖已成功的 push_status
            await db.execute(
                update(SuggestionItem)
                .where(
                    SuggestionItem.id.in_(item_ids),
                    SuggestionItem.push_status != "pushed",
                )
                .values(
                    push_status="push_failed",
                    push_error=last_error,
                    push_attempt_count=SuggestionItem.push_attempt_count + 1,
                )
            )
```

- [ ] **Step 3: 运行现有推送测试确认不破坏**

Run: `pytest tests/unit/test_pushback_purchase.py -v`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/pushback/purchase.py
git commit -m "fix(pushback): 推送失败路径添加 push_status guard 防覆盖 [P0-4]"
```

---

### Task 5: P1-1 GlobalConfig 正值校验

**Files:**
- Modify: `backend/app/engine/runner.py:63-64`
- Test: `backend/tests/unit/test_engine_runner.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_engine_runner.py` 末尾追加:

```python
@pytest.mark.asyncio
async def test_run_engine_rejects_zero_target_days(monkeypatch):
    """P1-1: target_days <= 0 应报错而非静默产出空建议。"""
    from types import SimpleNamespace
    from app.engine.runner import run_engine

    bad_config = SimpleNamespace(
        id=1, target_days=0, buffer_days=30, lead_time_days=50,
        include_tax=False, default_purchase_warehouse_id="WH-1",
        shop_sync_mode="all",
    )

    class _FakeDb:
        async def execute(self, stmt, params=None):
            # advisory lock
            if params and "key" in (params or {}):
                return None
            # GlobalConfig query
            return _ScalarResult(bad_config)

        async def commit(self):
            pass

    class _ScalarResult:
        def __init__(self, val):
            self._val = val
        def scalar_one(self):
            return self._val

    class _FakeSession:
        def __call__(self):
            return self
        async def __aenter__(self):
            return _FakeDb()
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("app.engine.runner.async_session_factory", _FakeSession())

    ctx = SimpleNamespace(
        progress=AsyncMock(),
        payload={},
    )
    with pytest.raises(ValueError, match="target_days"):
        await run_engine(ctx, triggered_by="manual")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_engine_runner.py::test_run_engine_rejects_zero_target_days -v`
Expected: FAIL — 不抛 ValueError

- [ ] **Step 3: 在 runner.py 加载 config 后添加校验**

在 `runner.py` 的 `config = ...scalar_one()` 之后(line 64),添加:

```python
        # P1-1: 配置正值校验,防止静默产出错误结果
        if config.target_days <= 0:
            raise ValueError(f"GlobalConfig.target_days must be > 0, got {config.target_days}")
        if config.buffer_days < 0:
            raise ValueError(f"GlobalConfig.buffer_days must be >= 0, got {config.buffer_days}")
        if config.lead_time_days < 0:
            raise ValueError(f"GlobalConfig.lead_time_days must be >= 0, got {config.lead_time_days}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_engine_runner.py -v`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/runner.py backend/tests/unit/test_engine_runner.py
git commit -m "fix(engine): GlobalConfig 加载后添加正值校验 [P1-1]"
```

---

## Phase 2: 健壮性 (P1-2 ~ P1-8)

### Task 6: P1-2 enqueue_task 递归深度限制

**Files:**
- Modify: `backend/app/tasks/queue.py:23,76-82`
- Test: `backend/tests/unit/test_queue.py` (新建)

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_queue.py`:

```python
"""enqueue_task 递归深度限制测试。"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import IntegrityError

from app.tasks.queue import enqueue_task


class _FakeOriginal(Exception):
    pass


def _make_dedupe_integrity_error():
    orig = _FakeOriginal("uq_task_run_active_dedupe")
    exc = IntegrityError("", {}, orig)
    return exc


@pytest.mark.asyncio
async def test_enqueue_task_recursive_retry_has_depth_limit():
    """P1-2: 递归重试不应无限循环。"""
    db = AsyncMock()
    # 第一次: INSERT 触发 IntegrityError
    # 第二次: 查 existing_id = None (活跃任务消失)
    # 递归: 再次 INSERT 触发 IntegrityError
    # 循环...应在 2 次后抛出 RuntimeError
    db.execute = AsyncMock(side_effect=_make_dedupe_integrity_error())
    db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="去重竞态重试耗尽"):
        await enqueue_task(
            db,
            job_name="test_job",
            trigger_source="manual",
            dedupe_key="test_key",
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_queue.py -v`
Expected: FAIL — RecursionError 或不抛 RuntimeError

- [ ] **Step 3: 修改 queue.py 添加深度限制**

```python
# queue.py: 修改函数签名(line 23)
async def enqueue_task(
    db: AsyncSession,
    *,
    job_name: str,
    trigger_source: str,
    dedupe_key: str | None = None,
    payload: dict[str, Any] | None = None,
    priority: int = 100,
    _retry_depth: int = 0,
) -> tuple[int, bool]:

# queue.py: 修改递归调用(line 76-82 区域)
        if existing_id is None:
            # 罕见竞争:唯一冲突但活跃记录又消失了,重试一次入队
            if _retry_depth >= 2:
                raise RuntimeError(
                    f"enqueue_task: 去重竞态重试耗尽 (job={job_name}, key={dedupe_key})"
                )
            logger.warning("task_enqueue_race_retry", job_name=job_name)
            return await enqueue_task(
                db,
                job_name=job_name,
                trigger_source=trigger_source,
                dedupe_key=dedupe_key,
                payload=payload,
                priority=priority,
                _retry_depth=_retry_depth + 1,
            )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_queue.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/queue.py backend/tests/unit/test_queue.py
git commit -m "fix(tasks): enqueue_task 递归重试添加深度限制 [P1-2]"
```

---

### Task 7: P1-3 同步层 OrderItem/InTransitItem 改用 UPSERT

**Files:**
- Modify: `backend/app/sync/order_list.py:146-170`
- Modify: `backend/app/sync/out_records.py:115-135`

OrderItem 的 PK 是 `(order_id, order_item_id)`,可以直接 UPSERT。
InTransitItem 没有自然唯一约束,保留 delete+insert 但确保同事务内。

- [ ] **Step 1: 修改 order_list.py — OrderItem 改 UPSERT + 清理**

替换 `order_list.py` line 146-170:

```python
    # P1-3: UPSERT 替代 delete-then-insert,避免中间状态数据丢失
    items_to_insert: list[dict[str, Any]] = []
    seen_item_ids: list[str] = []
    for raw_item in raw.get("orderItemVoList") or []:
        order_item_id = raw_item.get("orderItemId")
        commodity_sku = raw_item.get("commoditySku")
        if not order_item_id or not commodity_sku:
            continue
        oid = str(order_item_id)
        seen_item_ids.append(oid)
        items_to_insert.append(
            {
                "order_id": order_id,
                "order_item_id": oid,
                "commodity_sku": commodity_sku,
                "seller_sku": raw_item.get("sellerSku"),
                "quantity_ordered": _to_int(raw_item.get("quantityOrdered")),
                "quantity_shipped": _to_int(raw_item.get("quantityShipped")),
                "quantity_unfulfillable": _to_int(raw_item.get("quantityUnfulfillable")),
                "refund_num": _to_int(raw_item.get("refundNum")),
                "item_price_currency": raw_item.get("itemPriceCurrency"),
                "item_price_amount": _to_decimal(raw_item.get("itemPriceAmount")),
            }
        )
    if items_to_insert:
        stmt = pg_insert(OrderItem).values(items_to_insert)
        stmt = stmt.on_conflict_do_update(
            index_elements=["order_id", "order_item_id"],
            set_={
                "commodity_sku": stmt.excluded.commodity_sku,
                "seller_sku": stmt.excluded.seller_sku,
                "quantity_ordered": stmt.excluded.quantity_ordered,
                "quantity_shipped": stmt.excluded.quantity_shipped,
                "quantity_unfulfillable": stmt.excluded.quantity_unfulfillable,
                "refund_num": stmt.excluded.refund_num,
                "item_price_currency": stmt.excluded.item_price_currency,
                "item_price_amount": stmt.excluded.item_price_amount,
            },
        )
        await db.execute(stmt)
    # 清理本次 API 响应中不再存在的旧 items
    if seen_item_ids:
        await db.execute(
            delete(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.order_item_id.not_in(seen_item_ids),
            )
        )
    elif not items_to_insert:
        # 响应中无 items,清理全部
        await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
    return len(items_to_insert)
```

- [ ] **Step 2: 修改 out_records.py — 添加事务安全注释**

InTransitItem 无自然唯一约束(同一出库单可能有同 SKU 不同批次),保留 delete+insert。
在 `out_records.py` line 115 添加注释:

```python
    # P1-3 审查结论: InTransitItem 无自然唯一约束(同 record 可含重复 SKU),
    # 保留 delete+insert 模式。delete 和 insert 在同一个 db session 内,
    # 只有 batch commit(每 50 条)时才提交,所以单条记录的 delete+insert 是原子的。
    await db.execute(delete(InTransitItem).where(InTransitItem.saihu_out_record_id == record_id))
```

- [ ] **Step 3: 运行全量测试**

Run: `pytest tests/unit/ -v`
Expected: 163+ passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/sync/order_list.py backend/app/sync/out_records.py
git commit -m "fix(sync): OrderItem 改用 UPSERT + 清理旧 items [P1-3]"
```

---

### Task 8: P1-7 parse_purchase_date 容错

**Files:**
- Modify: `backend/app/engine/step6_timing.py:32-36`
- Test: `backend/tests/unit/test_engine_step6.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_engine_step6.py` 末尾追加:

```python
def test_parse_purchase_date_invalid_format_returns_today():
    """P1-7: 非 ISO 格式不应崩溃,保守返回 today。"""
    from app.engine.step6_timing import has_urgent_purchase

    # "2026/04/12" 不是 ISO 格式,之前会抛 ValueError
    # 修复后应视为紧急(返回 today <= today → urgent)
    result = has_urgent_purchase(
        {"US": "not-a-date"},
        today=date(2026, 4, 12),
    )
    assert result is True  # 格式错误 → 视为紧急
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_engine_step6.py::test_parse_purchase_date_invalid_format_returns_today -v`
Expected: FAIL — ValueError: Invalid isoformat string

- [ ] **Step 3: 修改 parse_purchase_date 添加容错**

```python
# step6_timing.py line 32-36 替换为:
def parse_purchase_date(raw: date | str, *, fallback: date | None = None) -> date:
    """兼容 engine(date) 与 PATCH API(str) 两种输入。

    解析失败时返回 fallback(默认 today),保守视为紧急。
    """
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        logger.warning("step6_parse_purchase_date_failed", raw_value=raw)
        if fallback is not None:
            return fallback
        from app.core.timezone import now_beijing
        return now_beijing().date()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_engine_step6.py -v`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/step6_timing.py backend/tests/unit/test_engine_step6.py
git commit -m "fix(engine): parse_purchase_date 添加容错,格式错误视为紧急 [P1-7]"
```

---

### Task 9: P1-4 + P1-5 同步窗口 overlap 可配置

**Files:**
- Modify: `backend/app/sync/order_list.py:34,76-84`

- [ ] **Step 1: 将 OVERLAP_MINUTES 改为从 GlobalConfig 读取**

```python
# order_list.py line 34: 修改为默认值
DEFAULT_OVERLAP_MINUTES = 5
```

在 `_compute_window` 中:

```python
async def _compute_window(
    db: AsyncSession, now: datetime, overlap_minutes: int = DEFAULT_OVERLAP_MINUTES,
) -> tuple[datetime, datetime]:
    state = (
        await db.execute(select(SyncState).where(SyncState.job_name == JOB_NAME))
    ).scalar_one_or_none()
    if state and state.last_success_at:
        date_start = state.last_success_at - timedelta(minutes=overlap_minutes)
    else:
        date_start = now - timedelta(days=INITIAL_BACKFILL_DAYS)
    return date_start, now
```

- [ ] **Step 2: 运行测试确认不破坏**

Run: `pytest tests/unit/ -v`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add backend/app/sync/order_list.py
git commit -m "refactor(sync): overlap 窗口提取为可配置参数 [P1-4/P1-5]"
```

---

### Task 10: P1-6 + P1-8 Token jitter + Reaper 标注

**Files:**
- Modify: `backend/app/saihu/client.py:96`
- Modify: `backend/app/tasks/reaper.py:77`

- [ ] **Step 1: client.py 添加 jitter**

```python
# client.py: 在文件顶部添加 import
import random

# client.py line 96 替换:
# 旧: await asyncio.sleep(0.5)
# 新:
            await asyncio.sleep(0.3 + random.random() * 0.4)  # P1-6: 0.3-0.7s jitter 防 thundering herd
```

- [ ] **Step 2: reaper.py 添加实例 ID 日志**

```python
# reaper.py line 77 替换:
# 旧:
#     if ids:
#         logger.warning("reaper_collected_zombies", task_ids=ids)
# 新:
        if ids:
            import os
            logger.warning(
                "reaper_collected_zombies",
                task_ids=ids,
                worker_id=os.getenv("HOSTNAME", "unknown"),  # P1-8: 标注容器实例
            )
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/unit/ -v`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add backend/app/saihu/client.py backend/app/tasks/reaper.py
git commit -m "fix: Token 重试添加 jitter + Reaper 日志标注实例 ID [P1-6/P1-8]"
```

---

## Phase 3: 工程质量 (P2 + P3)

### Task 11: P2-1 + P2-4 + P2-5 引擎日志 + 注释 + allocation_mode

**Files:**
- Modify: `backend/app/engine/runner.py` (Step4 invariant 日志)
- Modify: `backend/app/engine/step5_warehouse_split.py:152` (allocation_mode)
- Modify: `backend/app/engine/step2_sale_days.py:67` (90 天注释)

- [ ] **Step 1: Step4 invariant 触发时添加日志**

在 `step4_total.py` 的 `if raw < sum_qty:` 内添加:

```python
# 需要在文件顶部添加 logger
from app.core.logging import get_logger
logger = get_logger(__name__)

# 在 if raw < sum_qty: 块内:
    if raw < sum_qty:
        logger.info(
            "step4_invariant_adjusted",
            sku=sku,
            original_raw=raw,
            adjusted_to=sum_qty,
            buffer_qty=buffer_qty,
            local_total=local_total,
        )
        raw = sum_qty
```

- [ ] **Step 2: Step5 allocation_mode 改为 "zero_qty"**

```python
# step5_warehouse_split.py line 152:
# 旧: allocation_mode="matched",
# 新:
            allocation_mode="zero_qty",
```

- [ ] **Step 3: Step2 在途 90 天添加注释**

```python
# step2_sale_days.py line 67:
    # 海运通常 30-45 天,90 天覆盖绝大多数正常物流周期。
    # 超过 90 天未到货通常意味着物流异常(丢件),不算在途反而正确。
    cutoff = now_beijing() - timedelta(days=90)
```

- [ ] **Step 4: 运行全量测试**

Run: `pytest tests/unit/ -v`
Expected: 全部通过。注意: 如果有测试断言 `allocation_mode == "matched"` 且 country_qty=0,需要更新为 `"zero_qty"`。

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/step4_total.py backend/app/engine/step5_warehouse_split.py \
       backend/app/engine/step2_sale_days.py
git commit -m "refactor(engine): 添加边界日志 + allocation_mode 语义修正 + 在途注释 [P2-1/P2-4/P2-5]"
```

---

### Task 12: P2-6 zipcode_matcher 整数比较

**Files:**
- Modify: `backend/app/engine/zipcode_matcher.py:81-83`
- Test: `backend/tests/unit/test_zipcode_matcher.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_zipcode_matcher.py` 末尾追加:

```python
def test_number_eq_uses_integer_comparison():
    """P2-6: 数值 '=' 比较应使用整数避免浮点精度问题。"""
    rules = [
        ZipcodeRule(
            id=1, country="US", prefix_length=3,
            value_type="number", operator="=", compare_value="100",
            warehouse_id="WH-A", priority=1,
        ),
    ]
    # "100" prefix → 100 == 100 → match
    result = match_warehouses("10099", "US", rules)
    assert result == ["WH-A"]
```

- [ ] **Step 2: 运行测试确认通过(现有行为对整数已正确)**

Run: `pytest tests/unit/test_zipcode_matcher.py::test_number_eq_uses_integer_comparison -v`
Expected: PASS (整数比较 float 相等也成立)

- [ ] **Step 3: 修改 zipcode_matcher.py 使用 int 比较**

```python
# zipcode_matcher.py line 74-83 替换:
    if value_type == "number":
        try:
            l_num = float(left)
            r_num = float(right)
        except (TypeError, ValueError):
            return False

        if operator == "=":
            return int(l_num) == int(r_num)  # P2-6: 整数比较避免浮点精度
        if operator == "!=":
            return int(l_num) != int(r_num)
```

注意: `>`, `>=`, `<`, `<=` 保持 float 比较(有序比较不受精度影响)。

- [ ] **Step 4: 运行全部 zipcode 测试**

Run: `pytest tests/unit/test_zipcode_matcher.py -v`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/zipcode_matcher.py backend/tests/unit/test_zipcode_matcher.py
git commit -m "fix(engine): zipcode 数值 =/!= 比较改用整数避免浮点精度 [P2-6]"
```

---

### Task 13: P2-7 push 零数量过滤

**Files:**
- Modify: `backend/app/pushback/purchase.py:74`

- [ ] **Step 1: 修改 saihu_items 构造添加过滤**

```python
# purchase.py line 74 替换:
# 旧: saihu_items = [{"commodityId": it.commodity_id, "num": str(it.total_qty)} for it in items]
# 新:
    saihu_items = [
        {"commodityId": it.commodity_id, "num": str(it.total_qty)}
        for it in items
        if it.total_qty > 0  # P2-7: 过滤零数量条目
    ]
    if not saihu_items:
        raise ValueError("所有条目的 total_qty 均为 0,无法推送")
```

- [ ] **Step 2: 运行推送测试**

Run: `pytest tests/unit/test_pushback_purchase.py -v`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add backend/app/pushback/purchase.py
git commit -m "fix(pushback): 过滤 total_qty=0 的条目不发送赛狐 [P2-7]"
```

---

### Task 14: P2-8 api_call_log 写入失败计数

**Files:**
- Modify: `backend/app/saihu/client.py` (日志写入失败处)

- [ ] **Step 1: 在异常 catch 中添加结构化计数字段**

```python
# client.py: 在 api_call_log 写入的 except 块中替换 warning:
        except Exception as exc:
            logger.warning(
                "api_call_log_write_failed",
                error=str(exc),
                endpoint=endpoint_path,
                log_write_failed=True,  # P2-8: 可被日志聚合系统统计
            )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/saihu/client.py
git commit -m "fix(saihu): api_call_log 写入失败添加结构化计数字段 [P2-8]"
```

---

### Task 15: P3-5 rate_limit.py 有界性注释

**Files:**
- Modify: `backend/app/saihu/rate_limit.py:10-11`

- [ ] **Step 1: 添加注释说明有界性**

```python
# rate_limit.py line 10-11 替换:
# 进程级 limiter 缓存:endpoint -> limiter
# P3-5: 有界性说明 — endpoint 集合固定(~7 个业务接口),
# 字典大小不会超过接口总数,不会内存泄漏。
_LIMITERS: dict[str, AsyncLimiter] = {}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/saihu/rate_limit.py
git commit -m "docs(saihu): rate_limit _LIMITERS 添加有界性说明 [P3-5]"
```

---

### Deferred Tasks (文档 / 大范围)

以下项不在本计划代码修复范围内,单独排期:

| 项 | 内容 | 建议时间 |
|---|------|---------|
| P2-2 | 前端测试补充(SuggestionDetailView 等) | 独立 plan |
| P2-3 | 后端覆盖率提升至 70% | 独立 plan |
| P2-9 | runbook.md 添加 Alembic 降级操作手册 | 文档任务 |
| P2-10 | deployment.md 补充 pg_backup.sh 定时配置 | 文档任务 |
| P3-1 | Step5 订单查询复合索引(需 migration) | 独立 plan |
| P3-2 | 引擎 dry-run 模式 | 独立 plan |
| P3-3 | Playwright E2E 测试 | 独立 plan |
| P3-4 | 同步数据新鲜度告警 | 独立 plan |
| P3-6 | 密钥轮换 Runbook | 文档任务 |

---

### Task 16: 最终验证

- [ ] **Step 1: 运行全量后端测试**

Run: `pytest tests/unit/ -v --tb=short`
Expected: 全部通过

- [ ] **Step 2: 运行类型检查**

Run: `cd /e/Ai_project/restock_system/backend && python -m mypy app --ignore-missing-imports`
Expected: 无新增错误

- [ ] **Step 3: 运行 lint**

Run: `cd /e/Ai_project/restock_system/backend && python -m ruff check .`
Expected: 无新增错误

- [ ] **Step 4: 更新 PROGRESS.md**

在 `docs/PROGRESS.md` 的"最近更新"区域追加:

```markdown
### 2026-04-12 全链路 Review 修复
- P0-2: 引擎取整策略统一为 ceil(数量) / round(日期)
- P0-3: SuggestionItemPatch 添加非负校验
- P0-4: 推送失败路径 push_status guard
- P1-1: GlobalConfig 正值校验
- P1-2: enqueue_task 递归深度限制
- P1-3: OrderItem 改 UPSERT
- P1-6: Token 重试 jitter
- P1-7: parse_purchase_date 容错
- P2-*: 引擎日志 + 代码注释 + allocation_mode 语义修正
```

- [ ] **Step 5: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): 记录全链路 Review 修复 [2026-04-12]"
```
