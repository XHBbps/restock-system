# 端到端引擎测试 + 逻辑链路优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立从"库存+订单+仓库数据 → 引擎6步 → 建议单生成"的端到端集成测试，同时修复审计发现的逻辑问题和前端边界 case。

**Architecture:** 基于现有 `tests/integration/conftest.py` 的真实 PostgreSQL 集成测试框架，通过 patch `async_session_factory` 注入测试 DB session，构造最小 fixture 数据集驱动 `run_engine` 全链路执行。逻辑修复和前端优化作为独立 task 跟进。

**Tech Stack:** pytest + asyncpg + PostgreSQL / Vue 3 + TypeScript + Element Plus

**前置条件:** `TEST_DATABASE_URL` 环境变量指向可用的 PostgreSQL 测试数据库

---

## Module A: 端到端集成测试（Task 1-4）

### Task 1: 集成测试 fixture 基础设施

**Files:**
- Modify: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_engine_e2e.py`

- [ ] **Step 1: 在 conftest.py 添加 engine session patch fixture**

```python
# backend/tests/integration/conftest.py 末尾追加

@pytest.fixture
async def engine_session_factory(db_engine):
    """Patch async_session_factory so run_engine uses the test DB."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from unittest.mock import patch

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    with patch("app.engine.runner.async_session_factory", factory):
        yield factory
```

- [ ] **Step 2: 创建 test_engine_e2e.py 骨架**

```python
# backend/tests/integration/test_engine_e2e.py
"""端到端引擎集成测试：库存+订单+仓库 → 引擎6步 → 建议单生成。

需要环境变量 TEST_DATABASE_URL 指向 PostgreSQL 测试库。
"""
import pytest
from app.tasks.jobs import JobContext


class _TestContext:
    """Minimal JobContext for testing."""

    def __init__(self):
        self.steps: list[str] = []
        self.payload: dict = {"triggered_by": "test"}

    async def progress(self, **kwargs):
        self.steps.append(kwargs.get("current_step", ""))


@pytest.mark.asyncio
class TestEngineE2E:
    """Engine end-to-end integration tests."""
    pass
```

- [ ] **Step 3: 运行验证骨架可被收集**

```bash
cd backend && TEST_DATABASE_URL=$DATABASE_URL .venv/Scripts/python.exe -m pytest tests/integration/test_engine_e2e.py --collect-only
```

- [ ] **Step 4: Commit**

```bash
git add tests/integration/conftest.py tests/integration/test_engine_e2e.py
git commit -m "test(engine): 端到端集成测试骨架 + engine session patch fixture"
```

---

### Task 2: Fixture 数据工厂

**Files:**
- Create: `backend/tests/integration/factories.py`

- [ ] **Step 1: 创建 fixture 数据工厂函数**

```python
# backend/tests/integration/factories.py
"""集成测试数据工厂——构造引擎运行所需的最小数据集。"""
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.timezone import BEIJING
from app.models.global_config import GlobalConfig
from app.models.sku import SkuConfig
from app.models.warehouse import Warehouse
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderHeader, OrderItem, OrderDetail
from app.models.product_listing import ProductListing


async def seed_global_config(db: AsyncSession, **overrides) -> GlobalConfig:
    """播种全局配置（id=1）。"""
    defaults = dict(
        id=1,
        buffer_days=30,
        target_days=60,
        lead_time_days=50,
        include_tax="0",
        shop_sync_mode="all",
        login_password_hash="$2b$12$test_hash_placeholder",
        scheduler_enabled=True,
        calc_enabled=True,
        calc_cron="0 8 * * *",
        sync_interval_minutes=60,
    )
    defaults.update(overrides)
    config = GlobalConfig(**defaults)
    db.add(config)
    await db.flush()
    return config


async def seed_sku(db: AsyncSession, sku: str = "SKU-TEST-001",
                   enabled: bool = True, lead_time_days: int | None = None) -> SkuConfig:
    """播种 SKU 配置。"""
    obj = SkuConfig(commodity_sku=sku, enabled=enabled, lead_time_days=lead_time_days)
    db.add(obj)
    await db.flush()
    return obj


async def seed_warehouse(db: AsyncSession, warehouse_id: str, name: str,
                         wtype: int, country: str | None = None) -> Warehouse:
    """播种仓库。type=1 本地仓, type=3 海外仓。"""
    wh = Warehouse(id=warehouse_id, name=name, type=wtype, country=country,
                   last_sync_at=datetime.now(BEIJING))
    db.add(wh)
    await db.flush()
    return wh


async def seed_inventory(db: AsyncSession, sku: str, warehouse_id: str,
                         country: str | None, available: int,
                         reserved: int = 0) -> InventorySnapshotLatest:
    """播种库存快照。"""
    inv = InventorySnapshotLatest(
        commodity_sku=sku, warehouse_id=warehouse_id,
        country=country, available=available, reserved=reserved,
    )
    db.add(inv)
    await db.flush()
    return inv


async def seed_order(db: AsyncSession, shop_id: str, order_id: str,
                     country: str, sku: str, qty_shipped: int,
                     purchase_date: datetime | None = None,
                     postal_code: str | None = None) -> tuple:
    """播种订单头 + 订单行 + 订单详情（如有邮编）。"""
    if purchase_date is None:
        purchase_date = datetime.now(BEIJING) - timedelta(days=3)
    header = OrderHeader(
        shop_id=shop_id, amazon_order_id=order_id,
        marketplace_id="ATVPDKIKX0DER", country_code=country,
        order_status="Shipped", purchase_date=purchase_date,
        last_update_date=purchase_date, last_sync_at=datetime.now(BEIJING),
    )
    db.add(header)
    await db.flush()
    item = OrderItem(
        order_id=header.id, order_item_id=f"{order_id}-ITEM-1",
        commodity_sku=sku, quantity_shipped=qty_shipped, refund_num=0,
    )
    db.add(item)
    if postal_code:
        detail = OrderDetail(
            shop_id=shop_id, amazon_order_id=order_id,
            postal_code=postal_code, country_code=country,
            fetched_at=datetime.now(BEIJING),
        )
        db.add(detail)
    await db.flush()
    return header, item


async def seed_product_listing(db: AsyncSession, sku: str,
                                commodity_id: str = "COMM-001",
                                shop_id: str = "SHOP-1") -> ProductListing:
    """播种产品信息（commodity_id 映射）。"""
    pl = ProductListing(
        commodity_sku=sku, commodity_id=commodity_id,
        shop_id=shop_id, marketplace_id="ATVPDKIKX0DER",
        seller_sku=f"SELLER-{sku}", is_matched=True,
        online_status="active", last_sync_at=datetime.now(BEIJING),
    )
    db.add(pl)
    await db.flush()
    return pl


async def seed_minimum_dataset(db: AsyncSession, today: date | None = None):
    """播种引擎端到端运行所需的最小数据集。返回 dict 便于断言。"""
    if today is None:
        today = date.today()

    config = await seed_global_config(db)
    sku = await seed_sku(db, "SKU-E2E-001")
    wh_local = await seed_warehouse(db, "WH-LOCAL", "国内仓", 1)
    wh_us = await seed_warehouse(db, "WH-US-001", "美国仓", 3, "US")

    await seed_inventory(db, "SKU-E2E-001", "WH-US-001", "US", available=100, reserved=20)
    await seed_inventory(db, "SKU-E2E-001", "WH-LOCAL", None, available=50, reserved=0)

    purchase_dt = datetime(today.year, today.month, today.day, 10, 0,
                           tzinfo=BEIJING) - timedelta(days=3)
    await seed_order(db, "SHOP-1", "ORD-E2E-001", "US", "SKU-E2E-001",
                     qty_shipped=5, purchase_date=purchase_dt, postal_code="90210")

    await seed_product_listing(db, "SKU-E2E-001")
    await db.commit()

    return {
        "sku": "SKU-E2E-001",
        "config": config,
        "local_stock": 50,
        "overseas_stock": 120,  # 100 available + 20 reserved
        "order_qty": 5,
        "country": "US",
    }
```

- [ ] **Step 2: Commit**

```bash
git add tests/integration/factories.py
git commit -m "test(engine): 集成测试数据工厂 factories.py"
```

---

### Task 3: Happy Path 端到端测试

**Files:**
- Modify: `backend/tests/integration/test_engine_e2e.py`

- [ ] **Step 1: 写 happy path 测试**

```python
# 在 TestEngineE2E 类中添加

async def test_engine_happy_path_generates_suggestion(
    self, engine_session_factory, db_session
):
    """完整链路：库存+订单+仓库 → 引擎6步 → 建议单生成。"""
    from app.engine.runner import run_engine
    from app.models.suggestion import Suggestion, SuggestionItem
    from sqlalchemy import select
    from tests.integration.factories import seed_minimum_dataset

    # Arrange: 播种最小数据集
    data = await seed_minimum_dataset(db_session)

    # Act: 运行引擎
    ctx = _TestContext()
    suggestion_id = await run_engine(ctx, triggered_by="test")

    # Assert: 建议单已生成
    assert suggestion_id is not None, "引擎应返回 suggestion_id"

    # 验证建议单头
    async with engine_session_factory() as db:
        sug = (await db.execute(
            select(Suggestion).where(Suggestion.id == suggestion_id)
        )).scalar_one()
        assert sug.status == "draft"
        assert sug.total_items >= 1
        assert sug.triggered_by == "test"

        # 验证建议条目
        items = (await db.execute(
            select(SuggestionItem).where(
                SuggestionItem.suggestion_id == suggestion_id
            )
        )).scalars().all()
        assert len(items) >= 1

        item = items[0]
        assert item.commodity_sku == data["sku"]
        assert item.total_qty > 0, "补货量应大于0"
        assert item.country_breakdown is not None
        assert "US" in item.country_breakdown
        assert item.velocity_snapshot is not None
        assert item.sale_days_snapshot is not None

    # 验证引擎步骤进度
    assert len(ctx.steps) >= 6, f"应有至少6步进度回调，实际 {len(ctx.steps)}"
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && TEST_DATABASE_URL=$DATABASE_URL .venv/Scripts/python.exe -m pytest tests/integration/test_engine_e2e.py -v -s
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_engine_e2e.py
git commit -m "test(engine): happy path 端到端集成测试 — 库存+订单+仓库→建议单"
```

---

### Task 4: 边界 Case 测试

**Files:**
- Modify: `backend/tests/integration/test_engine_e2e.py`

- [ ] **Step 1: 无启用 SKU 早退**

```python
async def test_engine_no_enabled_sku_returns_none(
    self, engine_session_factory, db_session
):
    """无启用 SKU 时引擎应早退返回 None。"""
    from app.engine.runner import run_engine
    from tests.integration.factories import seed_global_config

    await seed_global_config(db_session)
    await db_session.commit()

    ctx = _TestContext()
    result = await run_engine(ctx, triggered_by="test")
    assert result is None
    assert any("无启用 SKU" in s or "完成" in s for s in ctx.steps)
```

- [ ] **Step 2: 零销量 SKU（velocity=0）**

```python
async def test_engine_zero_velocity_sku_produces_zero_qty(
    self, engine_session_factory, db_session
):
    """有库存但无订单的 SKU 应产生 total_qty=0 的建议条目。"""
    from app.engine.runner import run_engine
    from app.models.suggestion import SuggestionItem
    from sqlalchemy import select
    from tests.integration.factories import (
        seed_global_config, seed_sku, seed_warehouse,
        seed_inventory, seed_product_listing,
    )

    await seed_global_config(db_session)
    await seed_sku(db_session, "SKU-ZERO-VEL")
    await seed_warehouse(db_session, "WH-LOCAL", "国内仓", 1)
    await seed_warehouse(db_session, "WH-US", "美国仓", 3, "US")
    await seed_inventory(db_session, "SKU-ZERO-VEL", "WH-US", "US", 100, 0)
    await seed_inventory(db_session, "SKU-ZERO-VEL", "WH-LOCAL", None, 50, 0)
    await seed_product_listing(db_session, "SKU-ZERO-VEL")
    await db_session.commit()

    ctx = _TestContext()
    sid = await run_engine(ctx, triggered_by="test")
    assert sid is not None

    async with engine_session_factory() as db:
        items = (await db.execute(
            select(SuggestionItem).where(SuggestionItem.suggestion_id == sid)
        )).scalars().all()
        # 零销量 SKU 不应产生建议条目（country_qty 全部为 0，被过滤）
        zero_vel_items = [i for i in items if i.commodity_sku == "SKU-ZERO-VEL"]
        for item in zero_vel_items:
            assert item.total_qty == 0 or len(zero_vel_items) == 0
```

- [ ] **Step 3: 多国多 SKU 场景**

```python
async def test_engine_multi_country_multi_sku(
    self, engine_session_factory, db_session
):
    """多 SKU + 多国订单应各自独立计算补货量。"""
    from app.engine.runner import run_engine
    from app.models.suggestion import SuggestionItem
    from sqlalchemy import select
    from tests.integration.factories import (
        seed_global_config, seed_sku, seed_warehouse,
        seed_inventory, seed_order, seed_product_listing,
    )

    await seed_global_config(db_session, target_days=30, buffer_days=10)
    await seed_sku(db_session, "SKU-A")
    await seed_sku(db_session, "SKU-B")
    await seed_warehouse(db_session, "WH-LOCAL", "国内仓", 1)
    await seed_warehouse(db_session, "WH-US", "美国仓", 3, "US")
    await seed_warehouse(db_session, "WH-GB", "英国仓", 3, "GB")

    # SKU-A: 美国有库存有订单
    await seed_inventory(db_session, "SKU-A", "WH-US", "US", 50, 0)
    await seed_inventory(db_session, "SKU-A", "WH-LOCAL", None, 100, 0)
    await seed_order(db_session, "S1", "ORD-A-US", "US", "SKU-A", 10)

    # SKU-B: 英国有库存有订单
    await seed_inventory(db_session, "SKU-B", "WH-GB", "GB", 30, 0)
    await seed_inventory(db_session, "SKU-B", "WH-LOCAL", None, 200, 0)
    await seed_order(db_session, "S1", "ORD-B-GB", "GB", "SKU-B", 8)

    await seed_product_listing(db_session, "SKU-A")
    await seed_product_listing(db_session, "SKU-B", commodity_id="COMM-B", shop_id="S1")
    await db_session.commit()

    ctx = _TestContext()
    sid = await run_engine(ctx, triggered_by="test")
    assert sid is not None

    async with engine_session_factory() as db:
        items = (await db.execute(
            select(SuggestionItem).where(SuggestionItem.suggestion_id == sid)
        )).scalars().all()
        skus = {i.commodity_sku for i in items}
        assert "SKU-A" in skus
        assert "SKU-B" in skus

        for item in items:
            assert item.country_breakdown is not None
            if item.commodity_sku == "SKU-A":
                assert "US" in item.country_breakdown
            elif item.commodity_sku == "SKU-B":
                assert "GB" in item.country_breakdown
```

- [ ] **Step 4: 运行全部集成测试**

```bash
cd backend && TEST_DATABASE_URL=$DATABASE_URL .venv/Scripts/python.exe -m pytest tests/integration/test_engine_e2e.py -v -s
```

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_engine_e2e.py
git commit -m "test(engine): 边界 case 集成测试 — 无 SKU / 零销量 / 多国多 SKU"
```

---

## Module B: 逻辑链路修复（Task 5-6，基于研究发现）

### Task 5: 逻辑问题修复

基于研究 agent 发现的 5 个潜在问题，评估并修复需要立即处理的：

- [ ] **Step 1: 审查 5 个发现，标记 fix/defer**

研究发现的 5 个问题及处理决策：

1. **Step 5 order_detail JOIN 静默排除** → defer（已知行为，fixture 需覆盖两种路径 ✅ Task 4 已处理）
2. **in_transit 使用 now() vs today** → defer（微秒级误差对业务无影响）
3. **_persist_suggestion 无 SAVEPOINT** → defer（事务 rollback 是预期行为，用户已在 M2 审计时确认）
4. **compute_total buffer_qty 只计算 country_qty>0 的国家** → defer（spec 明确要求）
5. **run_engine 与 async_session_factory 强绑定** → defer（集成测试已用 patch 方案解决）

- [ ] **Step 2: Commit 发现记录**

将 5 个发现及决策记入 docs/superpowers/scorecard/ 或 PROGRESS.md。

---

### Task 6: 前端交互与边界优化（高频页面扫描）

- [ ] **Step 1: 用 agent 扫描前端高频页面的交互边界 case**

重点关注：
- SuggestionListView：跨页选择 + 推送流程的 loading/error/empty 状态
- DataOrdersView / DataInventoryView：5000 条本地分页的极端情况
- GlobalConfigView：保存后的参数变更提示
- TaskProgress：断网重连 + 终态处理

- [ ] **Step 2: 修复发现的前端 edge case**

- [ ] **Step 3: 运行前端测试验证**

```bash
cd frontend && npx vue-tsc --noEmit && npm run test
```

- [ ] **Step 4: Commit**

---

## 执行顺序

1. **Task 1** → Task 2 → Task 3 → Task 4（Module A，核心交付）
2. **Task 5**（Module B，审查+记录）
3. **Task 6**（Module C，前端优化）

每个 Task 完成后 checkpoint，确认无误再继续。
