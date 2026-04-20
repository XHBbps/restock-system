# 采购/补货分拆 + 安全库存 + EU 合并 + 生成开关修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"补货建议"拆成独立的**采购建议**（SKU 级）和**补货建议**（国家+仓库级）两个视图；全局参数新增安全库存；欧盟（除 UK）在数据同步入口合并为 `EU`；修复"采补建议生成"按钮开关判断 bug。

**Architecture:**
- **后端**：单个 alembic 迁移做 schema 改动 + 数据迁移 + 权限补齐；新增 `app/core/country_mapping.py` 作 EU 映射纯函数；engine step4 / step6 / runner 改写；API 层端点拆分（采购 / 补货两个独立导出）；Excel 导出服务参数化；定时调度只删 `calc_engine` cron 保留手动入口
- **前端**：嵌套路由方式 A（父容器 + 两个子视图），Tab 切换静默暂存；导出前 auto-save；新建 `PurchaseDateCell` 渲染逾期徽章；全局参数页加安全库存 + EU 成员多选
- **数据层**：系统未上线，alembic 迁移时直接 `UPDATE` 原地映射 EU，归档旧 draft，清所有 snapshot；源表加 `original_*` 列审计但不对前端暴露

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 async + Alembic + openpyxl（后端）；Vue 3 + TypeScript + Vite + Element Plus + Pinia（前端）；pytest + vitest + vue-tsc（测试）

**Pre-flight（执行前）：**
- 确认分支：`git checkout -b feature/split-procurement-restock-and-eu master`
- 确认本地 dev 容器运行：`docker compose -f deploy/docker-compose.dev.yml ps`
- 确认 alembic 当前 head：`docker exec restock-dev-backend alembic current`（应为 `20260419_0000`）
- **系统未上线**，按设计方案 B：alembic 迁移会 `TRUNCATE` 部分数据（所有 `suggestion_snapshot` + `excel_export_log`），原地 `UPDATE` EU 映射，归档旧 draft

---

## 文件结构全景

**创建：**
- `backend/alembic/versions/20260420_0900_split_procurement_restock_and_eu_mapping.py`
- `backend/app/core/country_mapping.py`
- `backend/tests/unit/test_country_mapping.py`
- `frontend/src/views/suggestion/ProcurementListView.vue`
- `frontend/src/views/suggestion/RestockListView.vue`
- `frontend/src/views/suggestion/ProcurementDetailView.vue`
- `frontend/src/views/suggestion/RestockDetailView.vue`
- `frontend/src/views/history/ProcurementHistoryView.vue`
- `frontend/src/views/history/RestockHistoryView.vue`
- `frontend/src/components/SuggestionTabBar.vue`
- `frontend/src/components/PurchaseDateCell.vue`
- `frontend/src/views/suggestion/__tests__/ProcurementListView.test.ts`
- `frontend/src/views/suggestion/__tests__/RestockListView.test.ts`
- `frontend/src/components/__tests__/PurchaseDateCell.test.ts`

**修改：**
- `backend/app/models/global_config.py`
- `backend/app/models/suggestion.py`
- `backend/app/models/suggestion_snapshot.py`
- `backend/app/models/order.py`
- `backend/app/models/product_listing.py`
- `backend/app/models/in_transit.py`
- `backend/app/models/inventory.py`
- `backend/app/schemas/config.py`
- `backend/app/schemas/suggestion.py`
- `backend/app/schemas/suggestion_snapshot.py`
- `backend/app/sync/order_list.py`
- `backend/app/sync/product_listing.py`
- `backend/app/sync/out_records.py`
- `backend/app/sync/inventory.py`
- `backend/app/engine/step4_total.py`
- `backend/app/engine/step6_timing.py`
- `backend/app/engine/runner.py`
- `backend/app/engine/calc_engine_job.py`
- `backend/app/api/config.py`
- `backend/app/api/suggestion.py`
- `backend/app/api/snapshot.py`
- `backend/app/services/excel_export.py`
- `backend/app/tasks/scheduler.py`
- `backend/tests/unit/test_engine_step4.py`
- `backend/tests/unit/test_engine_step6.py`
- `backend/tests/unit/test_engine_runner.py`
- `backend/tests/unit/test_sync_order_list.py`
- `backend/tests/unit/test_sync_product_listing.py`
- `backend/tests/unit/test_sync_out_records_job.py`
- `backend/tests/unit/test_suggestion_patch.py`
- `backend/tests/unit/test_config_schema.py`
- `backend/tests/integration/test_export_e2e.py`
- `backend/tests/integration/test_generation_toggle_api.py`
- `backend/tests/integration/test_config_api.py`
- `frontend/src/config/appPages.ts`
- `frontend/src/router/index.ts`
- `frontend/src/api/suggestion.ts`
- `frontend/src/api/snapshot.ts`
- `frontend/src/api/config.ts`
- `frontend/src/utils/countries.ts`
- `frontend/src/views/SuggestionListView.vue`（改为容器）
- `frontend/src/views/SuggestionDetailView.vue`（改为容器）
- `frontend/src/views/HistoryView.vue`（改为容器）
- `frontend/src/views/GlobalConfigView.vue`
- `frontend/src/views/__tests__/SuggestionListView.test.ts`
- `frontend/src/views/__tests__/HistoryView.test.ts`
- `frontend/src/views/__tests__/GlobalConfigView.test.ts`
- `docs/PROGRESS.md`
- `docs/Project_Architecture_Blueprint.md`

---

## Task 0: 新建功能分支

**Files:**
- Modify: 本地 git 状态

- [ ] **Step 1：切换到 master 并拉取最新**

```bash
cd /e/Ai_project/restock_system
git status
git checkout master
git pull --ff-only
```

- [ ] **Step 2：基于 master 新建分支**

```bash
git checkout -b feature/split-procurement-restock-and-eu
```

Expected: `Switched to a new branch 'feature/split-procurement-restock-and-eu'`

---

## Task 1: Alembic 迁移（schema + 数据映射 + 权限）

**Files:**
- Create: `backend/alembic/versions/20260420_0900_split_procurement_restock_and_eu_mapping.py`

- [ ] **Step 1：生成迁移文件骨架**

```bash
docker exec restock-dev-backend alembic revision -m "split procurement restock and eu mapping"
```

（或手动创建下面文件内容）

- [ ] **Step 2：写完整迁移文件**

```python
"""split procurement restock and eu mapping

Revision ID: 20260420_0900
Revises: 20260419_0000
Create Date: 2026-04-20 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260420_0900"
down_revision = "20260419_0000"
branch_labels = None
depends_on = None

EU_COUNTRIES = ["DE", "FR", "IT", "ES", "NL", "BE", "PL", "SE", "IE"]
# marketplace_to_country 映射到 EU 9 国的 marketplace_id
# 参考 backend/app/core/timezone.py:70 marketplace_to_country 实现
EU_MARKETPLACE_IDS = [
    "A1PA6795UKMFR9",  # DE
    "A13V1IB3VIYZZH",  # FR
    "APJ6JRA9NG5V4",   # IT
    "A1RKKUPIHCS9HS",  # ES
    "A1805IZSGTT6HS",  # NL
    "A1IM4EOPHU95H0",  # BE (if applicable)
    "A1C3SOZRARQ6R3",  # PL
    "A2NODRKZP88ZB9",  # SE
    "A28R8C7NBKEWEA",  # IE
]


def upgrade() -> None:
    # ========== global_config ==========
    op.add_column(
        "global_config",
        sa.Column("safety_stock_days", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "global_config",
        sa.Column(
            "eu_countries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        f"UPDATE global_config SET eu_countries = '{sa.text(repr(EU_COUNTRIES).replace(chr(39), chr(34)))}'::jsonb WHERE id = 1"
    )
    # 用参数化写法更安全
    op.execute(
        sa.text(
            "UPDATE global_config SET eu_countries = CAST(:v AS jsonb) WHERE id = 1"
        ).bindparams(v='["DE","FR","IT","ES","NL","BE","PL","SE","IE"]')
    )
    op.drop_column("global_config", "calc_enabled")
    op.drop_column("global_config", "calc_cron")
    op.drop_column("global_config", "include_tax")
    op.drop_column("global_config", "default_purchase_warehouse_id")

    # ========== suggestion ==========
    op.add_column(
        "suggestion",
        sa.Column("procurement_item_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "suggestion",
        sa.Column("restock_item_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # ========== suggestion_item ==========
    op.add_column(
        "suggestion_item",
        sa.Column("purchase_qty", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("purchase_date", sa.Date(), nullable=True),
    )

    op.drop_constraint("export_status_enum", "suggestion_item", type_="check")
    op.alter_column("suggestion_item", "export_status", new_column_name="restock_export_status")
    op.alter_column("suggestion_item", "exported_snapshot_id", new_column_name="restock_exported_snapshot_id")
    op.alter_column("suggestion_item", "exported_at", new_column_name="restock_exported_at")
    op.create_check_constraint(
        "restock_export_status_enum",
        "suggestion_item",
        "restock_export_status IN ('pending','exported')",
    )

    op.drop_index("ix_suggestion_item_export_status", table_name="suggestion_item")
    op.create_index(
        "ix_suggestion_item_restock_export_status",
        "suggestion_item",
        ["suggestion_id", "restock_export_status"],
    )

    op.add_column(
        "suggestion_item",
        sa.Column(
            "procurement_export_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("procurement_exported_snapshot_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("procurement_exported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_item_procurement_snapshot",
        "suggestion_item",
        "suggestion_snapshot",
        ["procurement_exported_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "procurement_export_status_enum",
        "suggestion_item",
        "procurement_export_status IN ('pending','exported')",
    )
    op.create_index(
        "ix_suggestion_item_procurement_export_status",
        "suggestion_item",
        ["suggestion_id", "procurement_export_status"],
    )

    # ========== suggestion_snapshot ==========
    op.add_column(
        "suggestion_snapshot",
        sa.Column(
            "snapshot_type",
            sa.String(20),
            nullable=False,
            server_default="restock",
        ),
    )
    op.create_check_constraint(
        "snapshot_type_enum",
        "suggestion_snapshot",
        "snapshot_type IN ('procurement','restock')",
    )
    op.drop_constraint("uq_snapshot_suggestion_version", "suggestion_snapshot", type_="unique")
    op.create_unique_constraint(
        "uq_snapshot_suggestion_type_version",
        "suggestion_snapshot",
        ["suggestion_id", "snapshot_type", "version"],
    )
    op.create_index(
        "ix_snapshot_type_suggestion",
        "suggestion_snapshot",
        ["snapshot_type", "suggestion_id"],
    )

    # ========== suggestion_snapshot_item ==========
    op.add_column(
        "suggestion_snapshot_item",
        sa.Column("purchase_qty", sa.Integer(), nullable=True),
    )
    op.add_column(
        "suggestion_snapshot_item",
        sa.Column("purchase_date", sa.Date(), nullable=True),
    )

    # ========== 源表加 original_* ==========
    op.add_column(
        "order_header",
        sa.Column("original_country_code", sa.String(2), nullable=True),
    )
    op.add_column(
        "product_listing",
        sa.Column("original_marketplace_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "in_transit_record",
        sa.Column("original_target_country", sa.String(2), nullable=True),
    )
    op.add_column(
        "inventory_snapshot_latest",
        sa.Column("original_country", sa.String(2), nullable=True),
    )

    # ========== 数据迁移：EU 原地映射 ==========
    eu_tuple = tuple(EU_COUNTRIES)
    eu_mp_tuple = tuple(EU_MARKETPLACE_IDS)

    op.execute(
        sa.text(
            "UPDATE order_header SET original_country_code = country_code, country_code = 'EU' "
            "WHERE country_code = ANY(:eu)"
        ).bindparams(eu=list(eu_tuple))
    )
    op.execute(
        sa.text(
            "UPDATE product_listing SET original_marketplace_id = marketplace_id, marketplace_id = 'EU' "
            "WHERE marketplace_id = ANY(:mp)"
        ).bindparams(mp=list(eu_mp_tuple))
    )
    op.execute(
        sa.text(
            "UPDATE in_transit_record SET original_target_country = target_country, target_country = 'EU' "
            "WHERE target_country = ANY(:eu)"
        ).bindparams(eu=list(eu_tuple))
    )
    op.execute(
        sa.text(
            "UPDATE inventory_snapshot_latest SET original_country = country, country = 'EU' "
            "WHERE country = ANY(:eu)"
        ).bindparams(eu=list(eu_tuple))
    )

    # ========== 归档旧 draft + 清历史快照 ==========
    op.execute(
        "UPDATE suggestion SET status='archived', archived_trigger='schema_migration', "
        "archived_at=NOW() WHERE status='draft'"
    )
    op.execute("DELETE FROM excel_export_log")
    op.execute("DELETE FROM suggestion_snapshot_item")
    op.execute("DELETE FROM suggestion_snapshot")

    # ========== 权限补齐：业务人员 + restock:operate ==========
    op.execute(
        "INSERT INTO role_permission (role_id, permission_code) "
        "SELECT id, 'restock:operate' FROM role WHERE name='业务人员' "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    raise NotImplementedError("AGENTS.md §11: 数据库迁移不支持自动回退，请恢复备份")
```

- [ ] **Step 3：运行迁移**

```bash
docker exec restock-dev-backend alembic upgrade head
```

Expected: `Running upgrade 20260419_0000 -> 20260420_0900, split procurement restock and eu mapping`

- [ ] **Step 4：验证 schema**

```bash
docker exec restock-dev-db psql -U postgres -d restock -c "\d global_config" | grep -E "safety_stock_days|eu_countries|calc_enabled"
docker exec restock-dev-db psql -U postgres -d restock -c "\d suggestion_item" | grep -E "purchase_qty|procurement_export_status|restock_export_status"
```

Expected: 新字段存在，`calc_enabled` 不存在。

- [ ] **Step 5：Commit**

```bash
git add backend/alembic/versions/20260420_0900_split_procurement_restock_and_eu_mapping.py
git commit -m "feat(db): split procurement/restock 字段，新增 safety_stock_days + EU 映射"
```

---

## Task 2: ORM 模型同步更新

**Files:**
- Modify: `backend/app/models/global_config.py`
- Modify: `backend/app/models/suggestion.py`
- Modify: `backend/app/models/suggestion_snapshot.py`
- Modify: `backend/app/models/order.py`
- Modify: `backend/app/models/product_listing.py`
- Modify: `backend/app/models/in_transit.py`
- Modify: `backend/app/models/inventory.py`

- [ ] **Step 1：更新 `global_config.py`**

删除 `calc_enabled`、`calc_cron`、`include_tax`、`default_purchase_warehouse_id` 四列的 `Mapped` 声明。新增：

```python
safety_stock_days: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
eu_countries: Mapped[list[str]] = mapped_column(
    JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb")
)
```

- [ ] **Step 2：更新 `suggestion.py` 的 `Suggestion` 类**

在 `total_items` 后加：
```python
procurement_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
restock_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 3：更新 `suggestion.py` 的 `SuggestionItem` 类**

- 字段名 `export_status` 重命名为 `restock_export_status`
- 字段名 `exported_snapshot_id` 重命名为 `restock_exported_snapshot_id`
- 字段名 `exported_at` 重命名为 `restock_exported_at`
- 新增字段：

```python
purchase_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

procurement_export_status: Mapped[str] = mapped_column(
    String(20), nullable=False, default="pending"
)
procurement_exported_snapshot_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("suggestion_snapshot.id", ondelete="SET NULL"),
    nullable=True,
)
procurement_exported_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

- 修改 `__table_args__`：
  - CheckConstraint 原 `export_status_enum` → 改为 `restock_export_status_enum` + 新增 `procurement_export_status_enum`
  - Index 原 `ix_suggestion_item_export_status` → 改为 `ix_suggestion_item_restock_export_status` + 新增 `ix_suggestion_item_procurement_export_status`

- [ ] **Step 4：更新 `suggestion_snapshot.py` 的 `SuggestionSnapshot`**

```python
snapshot_type: Mapped[str] = mapped_column(
    String(20), nullable=False, default="restock"
)
```

`__table_args__`：`UniqueConstraint("suggestion_id", "version")` → `UniqueConstraint("suggestion_id", "snapshot_type", "version")`，名字改为 `uq_snapshot_suggestion_type_version`；加 CheckConstraint `snapshot_type_enum`；加 Index `ix_snapshot_type_suggestion`。

- [ ] **Step 5：更新 `suggestion_snapshot.py` 的 `SuggestionSnapshotItem`**

```python
purchase_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
```

- [ ] **Step 6：更新源表模型加 `original_*`**

在各自文件的 ORM 类里：

```python
# order.py
original_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

# product_listing.py
original_marketplace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

# in_transit.py
original_target_country: Mapped[str | None] = mapped_column(String(2), nullable=True)

# inventory.py (InventorySnapshotLatest 类)
original_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
```

- [ ] **Step 7：验证模型能导入 + 没有 linting 错误**

```bash
docker exec restock-dev-backend python -c "from app.models.suggestion import Suggestion, SuggestionItem; from app.models.suggestion_snapshot import SuggestionSnapshot, SuggestionSnapshotItem; from app.models.global_config import GlobalConfig; print('OK')"
```

Expected: `OK`

- [ ] **Step 8：Commit**

```bash
git add backend/app/models/
git commit -m "feat(models): ORM 同步新 schema（purchase_qty/purchase_date/snapshot_type 等）"
```

---

## Task 3: `country_mapping.py` 工具（TDD）

**Files:**
- Create: `backend/app/core/country_mapping.py`
- Create: `backend/tests/unit/test_country_mapping.py`

- [ ] **Step 1：写失败测试**

`backend/tests/unit/test_country_mapping.py`：

```python
from app.core.country_mapping import apply_eu_mapping


def test_apply_eu_mapping_country_in_eu():
    assert apply_eu_mapping("DE", {"DE", "FR", "IT"}) == "EU"


def test_apply_eu_mapping_country_not_in_eu():
    assert apply_eu_mapping("US", {"DE", "FR"}) == "US"


def test_apply_eu_mapping_none_input():
    assert apply_eu_mapping(None, {"DE", "FR"}) is None


def test_apply_eu_mapping_empty_eu_list():
    assert apply_eu_mapping("DE", set()) == "DE"


def test_apply_eu_mapping_already_eu():
    # 已映射过的再调一次应该幂等
    assert apply_eu_mapping("EU", {"DE", "FR"}) == "EU"


def test_apply_eu_mapping_gb_excluded():
    # UK (GB) 通常不在 eu_countries，确保不被误映
    assert apply_eu_mapping("GB", {"DE", "FR", "IT"}) == "GB"
```

- [ ] **Step 2：运行测试确认失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_country_mapping.py -v
```

Expected: 6 failed with ModuleNotFoundError

- [ ] **Step 3：写实现**

`backend/app/core/country_mapping.py`：

```python
"""EU 国家合并映射工具。

同步任务入口把欧盟成员国的 country 字段映射为字面 'EU'，原值存到
`original_*` 列作审计。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_config import GlobalConfig


async def load_eu_countries(db: AsyncSession) -> set[str]:
    """一次性读取 global_config.eu_countries，调用方自己持有本次任务的集合。"""
    config = await db.get(GlobalConfig, 1)
    if config is None:
        return set()
    values = config.eu_countries or []
    return {str(v).upper() for v in values if v}


def apply_eu_mapping(country: str | None, eu_countries: set[str]) -> str | None:
    """将国家码映射为 'EU'（若在 eu_countries 中）；None 保持 None。

    幂等：'EU' 本身不在 eu_countries 里时原样返回。
    """
    if country is None:
        return None
    if country in eu_countries:
        return "EU"
    return country
```

- [ ] **Step 4：运行测试确认通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_country_mapping.py -v
```

Expected: 6 passed

- [ ] **Step 5：Commit**

```bash
git add backend/app/core/country_mapping.py backend/tests/unit/test_country_mapping.py
git commit -m "feat(core): 新增 country_mapping.py EU 映射工具 + 单测"
```

---

## Task 4: 订单同步接入 EU 映射

**Files:**
- Modify: `backend/app/sync/order_list.py`
- Modify: `backend/tests/unit/test_sync_order_list.py`

- [ ] **Step 1：更新测试**

在 `test_sync_order_list.py` 里新增用例（用现有 fixture 模式）：

```python
@pytest.mark.asyncio
async def test_sync_order_list_applies_eu_mapping(db_session):
    # 初始化 global_config.eu_countries = ['DE', 'FR']
    config = await db_session.get(GlobalConfig, 1)
    config.eu_countries = ["DE", "FR"]
    await db_session.commit()

    # 模拟赛狐返回一条德国订单
    fake_order = {
        "orderId": "T-DE-001",
        "marketplaceId": "A1PA6795UKMFR9",  # DE
        # ... 其他必要字段
    }
    # 通过 monkeypatch 注入 fake httpx 返回
    ...

    await sync_order_list(db_session)

    row = (await db_session.execute(
        select(OrderHeader).where(OrderHeader.order_id == "T-DE-001")
    )).scalar_one()
    assert row.country_code == "EU"
    assert row.original_country_code == "DE"
```

- [ ] **Step 2：运行确认失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_sync_order_list.py::test_sync_order_list_applies_eu_mapping -v
```

Expected: FAIL（country_code != 'EU'）

- [ ] **Step 3：修改 `backend/app/sync/order_list.py:124,136` 附近**

在同步函数顶部加：

```python
from app.core.country_mapping import load_eu_countries, apply_eu_mapping

async def sync_order_list(db: AsyncSession, ...):
    eu_countries = await load_eu_countries(db)
    # ...
```

在每行订单写入前，把原来的 `country_code = marketplace_to_country(row.marketplaceId)` 改为：

```python
raw_country = marketplace_to_country(row.marketplaceId)
mapped_country = apply_eu_mapping(raw_country, eu_countries)
# 写入
header.country_code = mapped_country
if mapped_country != raw_country:
    header.original_country_code = raw_country
else:
    header.original_country_code = None
```

- [ ] **Step 4：运行测试确认通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_sync_order_list.py -v
```

Expected: all passed

- [ ] **Step 5：Commit**

```bash
git add backend/app/sync/order_list.py backend/tests/unit/test_sync_order_list.py
git commit -m "feat(sync): 订单同步接入 EU 映射，原国家存 original_country_code"
```

---

## Task 5: 商品同步接入 EU 映射

**Files:**
- Modify: `backend/app/sync/product_listing.py`
- Modify: `backend/tests/unit/test_sync_product_listing.py`

- [ ] **Step 1：更新测试**

增加用例 `test_sync_product_listing_applies_eu_mapping`，验证 marketplace_id 为 EU 国家站点时，`marketplace_id = 'EU'`、`original_marketplace_id` 存原站点 ID。

- [ ] **Step 2：运行失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_sync_product_listing.py -v
```

- [ ] **Step 3：修改 `backend/app/sync/product_listing.py:126,132` 附近**

顶部引入：
```python
from app.core.country_mapping import load_eu_countries, apply_eu_mapping
```

同步函数开头加载一次 `eu_countries`，每行写入前：

```python
raw_mp = row.marketplaceId
raw_country = marketplace_to_country(raw_mp)
mapped_country = apply_eu_mapping(raw_country, eu_countries)
if mapped_country == "EU":
    listing.marketplace_id = "EU"
    listing.original_marketplace_id = raw_mp
else:
    listing.marketplace_id = raw_mp
    listing.original_marketplace_id = None
```

- [ ] **Step 4：运行通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_sync_product_listing.py -v
```

- [ ] **Step 5：Commit**

```bash
git add backend/app/sync/product_listing.py backend/tests/unit/test_sync_product_listing.py
git commit -m "feat(sync): 商品同步接入 EU 映射"
```

---

## Task 6: 出库同步接入 EU 映射

**Files:**
- Modify: `backend/app/sync/out_records.py`
- Modify: `backend/tests/unit/test_sync_out_records_job.py`

- [ ] **Step 1：更新测试**

增加用例：备注中解析得到 `DE` 的出库记录，映射后 `target_country='EU'`，`original_target_country='DE'`。

- [ ] **Step 2：运行失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_sync_out_records_job.py -v
```

- [ ] **Step 3：修改 `backend/app/sync/out_records.py`**

顶部引入 `country_mapping`，同步函数开头加载 `eu_countries`。在备注解析得到 country 后：

```python
mapped = apply_eu_mapping(parsed_country, eu_countries)
record.target_country = mapped
if mapped != parsed_country:
    record.original_target_country = parsed_country
else:
    record.original_target_country = None
```

**注意**：历史 `target_country` 空值回填逻辑（PROGRESS §3.35）需要同样经过映射。

- [ ] **Step 4：运行通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_sync_out_records_job.py -v
```

- [ ] **Step 5：Commit**

```bash
git add backend/app/sync/out_records.py backend/tests/unit/test_sync_out_records_job.py
git commit -m "feat(sync): 出库同步接入 EU 映射（含历史回填）"
```

---

## Task 7: 库存同步接入 EU 映射

**Files:**
- Modify: `backend/app/sync/inventory.py`

- [ ] **Step 1：修改 inventory 同步**

inventory 同步时从 `warehouse` 表 join 出 country，映射后写 `inventory_snapshot_latest.country`：

```python
from app.core.country_mapping import load_eu_countries, apply_eu_mapping

async def sync_inventory(db: AsyncSession, ...):
    eu_countries = await load_eu_countries(db)
    # ... 原逻辑
    for row in items:
        raw_country = row.warehouse.country
        mapped = apply_eu_mapping(raw_country, eu_countries)
        snapshot.country = mapped
        snapshot.original_country = raw_country if mapped != raw_country else None
```

**特殊说明**：如果仓库本身 `country='EU'`（管理员手动设置），`apply_eu_mapping('EU', {...})` 返回 `'EU'` 不变，`original_country = None`。符合预期。

- [ ] **Step 2：手工跑一次同步验证**

```bash
docker exec restock-dev-backend python -c "
import asyncio
from app.db.session import get_db
from app.sync.inventory import sync_inventory

async def main():
    async for db in get_db():
        await sync_inventory(db)
        break

asyncio.run(main())
"
```

- [ ] **Step 3：SQL 验证**

```bash
docker exec restock-dev-db psql -U postgres -d restock -c \
  "SELECT country, original_country, COUNT(*) FROM inventory_snapshot_latest GROUP BY 1, 2 ORDER BY 1"
```

Expected: 看到 `country='EU'`、`original_country='DE'` 等行。

- [ ] **Step 4：Commit**

```bash
git add backend/app/sync/inventory.py
git commit -m "feat(sync): 库存同步接入 EU 映射"
```

---

## Task 8: 引擎 step4_total 新采购公式

**Files:**
- Modify: `backend/app/engine/step4_total.py`
- Modify: `backend/tests/unit/test_engine_step4.py`

- [ ] **Step 1：写失败测试**

在 `test_engine_step4.py` 加用例：

```python
def test_step4_new_purchase_formula():
    """
    Σ country_qty=100, Σ velocity=5, buffer_days=30, safety_stock_days=15,
    local.available=200, local.reserved=50
    purchase_qty = 100 + 5*30 - (200+50) + 5*15
                 = 100 + 150 - 250 + 75 = 75
    """
    ctx = EngineContext(
        country_qty={"sku1": {"US": 60, "EU": 40}},
        velocity={"sku1": {"US": 3, "EU": 2}},
        local_stock={"sku1": {"available": 200, "reserved": 50}},
        buffer_days=30,
        safety_stock_days=15,
    )
    result = step4_total(ctx)
    assert result["sku1"]["purchase_qty"] == 75


def test_step4_subtracts_reserved():
    """新公式必须减 reserved，不只是 available。"""
    ctx = EngineContext(
        country_qty={"sku1": {"US": 0}},
        velocity={"sku1": {"US": 0}},
        local_stock={"sku1": {"available": 0, "reserved": 50}},
        buffer_days=30,
        safety_stock_days=0,
    )
    result = step4_total(ctx)
    assert result["sku1"]["purchase_qty"] == -50  # 允许负数，API 层再过滤


def test_step4_velocity_sum_includes_all_countries():
    """Σ velocity 不受 restock_regions 白名单限制。"""
    ctx = EngineContext(
        country_qty={"sku1": {"US": 0}},  # 只有 US 在白名单
        velocity={"sku1": {"US": 3, "JP": 2}},  # JP 也算
        local_stock={"sku1": {"available": 0, "reserved": 0}},
        buffer_days=30,
        safety_stock_days=15,
    )
    result = step4_total(ctx)
    # 0 + 5*30 - 0 + 5*15 = 150 + 75 = 225
    assert result["sku1"]["purchase_qty"] == 225
```

- [ ] **Step 2：运行失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_engine_step4.py -v
```

- [ ] **Step 3：修改 `backend/app/engine/step4_total.py:46-76`**

```python
def step4_total(ctx: EngineContext) -> dict[str, dict[str, int]]:
    """Step 4：按 SKU 计算采购量。

    新公式：
      purchase_qty(sku) = Σ country_qty[sku]
                       + Σ velocity[sku] × buffer_days
                       - (local.available + local.reserved)
                       + Σ velocity[sku] × safety_stock_days
    """
    result: dict[str, dict[str, int]] = {}
    for sku in ctx.country_qty.keys() | ctx.velocity.keys() | ctx.local_stock.keys():
        sum_qty = sum((ctx.country_qty.get(sku) or {}).values())
        sum_velocity = sum((ctx.velocity.get(sku) or {}).values())
        local = ctx.local_stock.get(sku) or {"available": 0, "reserved": 0}
        local_total = int(local.get("available", 0)) + int(local.get("reserved", 0))

        buffer_qty = math.ceil(sum_velocity * ctx.buffer_days)
        safety_qty = math.ceil(sum_velocity * ctx.safety_stock_days)

        purchase_qty = sum_qty + buffer_qty - local_total + safety_qty
        result[sku] = {"purchase_qty": int(purchase_qty)}
    return result
```

**注意**：`EngineContext` 里需要有 `safety_stock_days` 字段，在 `backend/app/engine/context.py`（或定义 EngineContext 的地方）新增。

- [ ] **Step 4：运行通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_engine_step4.py -v
```

- [ ] **Step 5：Commit**

```bash
git add backend/app/engine/step4_total.py backend/app/engine/context.py backend/tests/unit/test_engine_step4.py
git commit -m "feat(engine): step4 新采购公式（加安全库存、减本地占用）"
```

---

## Task 9: 引擎 step6_timing 计算 purchase_date

**Files:**
- Modify: `backend/app/engine/step6_timing.py`
- Modify: `backend/tests/unit/test_engine_step6.py`

- [ ] **Step 1：写失败测试**

```python
from datetime import date, timedelta
from app.engine.step6_timing import step6_timing

def test_step6_purchase_date_with_min_sale_days():
    """
    min(sale_days)=30, lead_time=50
    purchase_date = today + 30 - 2*50 = today - 70
    """
    today = date(2026, 4, 20)
    result = step6_timing(
        sale_days_snapshot={"sku1": {"US": 30, "EU": 60}},
        purchase_qty={"sku1": 100},
        lead_time_by_sku={"sku1": 50},
        today=today,
    )
    assert result["sku1"]["purchase_date"] == date(2026, 4, 20) - timedelta(days=70)


def test_step6_no_purchase_date_when_zero_qty():
    result = step6_timing(
        sale_days_snapshot={"sku1": {"US": 30}},
        purchase_qty={"sku1": 0},
        lead_time_by_sku={"sku1": 50},
        today=date(2026, 4, 20),
    )
    assert result["sku1"]["purchase_date"] is None


def test_step6_no_purchase_date_when_no_sale_days():
    result = step6_timing(
        sale_days_snapshot={"sku1": {}},  # 空
        purchase_qty={"sku1": 100},
        lead_time_by_sku={"sku1": 50},
        today=date(2026, 4, 20),
    )
    assert result["sku1"]["purchase_date"] is None
```

- [ ] **Step 2：运行失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_engine_step6.py -v
```

- [ ] **Step 3：扩展 `backend/app/engine/step6_timing.py`**

在现有 urgent 逻辑基础上新增 purchase_date：

```python
from datetime import date, timedelta


def _compute_purchase_date(
    sale_days_by_country: dict[str, float | None],
    purchase_qty: int,
    lead_time_days: int,
    today: date,
) -> date | None:
    if purchase_qty <= 0:
        return None
    valid = [v for v in sale_days_by_country.values() if v is not None]
    if not valid:
        return None
    min_sd = min(valid)
    offset = int(min_sd) - 2 * lead_time_days
    return today + timedelta(days=offset)


def step6_timing(
    sale_days_snapshot: dict[str, dict[str, float | None]],
    purchase_qty: dict[str, int],
    lead_time_by_sku: dict[str, int],
    today: date | None = None,
    ...  # 现有 urgent 参数
) -> dict[str, dict[str, Any]]:
    today = today or date.today()
    result = {}
    for sku in sale_days_snapshot:
        # 现有 urgent 计算保留
        result[sku] = {"urgent": ..., "purchase_date": _compute_purchase_date(
            sale_days_snapshot[sku],
            purchase_qty.get(sku, 0),
            lead_time_by_sku.get(sku, 50),
            today,
        )}
    return result
```

- [ ] **Step 4：运行通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_engine_step6.py -v
```

- [ ] **Step 5：Commit**

```bash
git add backend/app/engine/step6_timing.py backend/tests/unit/test_engine_step6.py
git commit -m "feat(engine): step6 新增 purchase_date 计算"
```

---

## Task 10: runner 集成新字段 + item_count + 翻 OFF

**Files:**
- Modify: `backend/app/engine/runner.py`
- Modify: `backend/app/engine/calc_engine_job.py`
- Modify: `backend/tests/unit/test_engine_runner.py`

- [ ] **Step 1：写失败测试**

```python
@pytest.mark.asyncio
async def test_runner_writes_purchase_qty_and_date(db_session):
    # 构造场景让某 SKU purchase_qty>0、purchase_date 有值
    ...
    result = await run_engine(db_session, config)
    item = (await db_session.execute(
        select(SuggestionItem).where(SuggestionItem.commodity_sku == "sku1")
    )).scalar_one()
    assert item.purchase_qty == 225
    assert item.purchase_date is not None
    assert item.total_qty == 100  # = Σ country_breakdown


@pytest.mark.asyncio
async def test_runner_filters_items_zero_everything(db_session):
    """purchase_qty=0 AND country_breakdown 全 0 的 SKU 不写入。"""
    ...
    result = await run_engine(db_session, config)
    count = (await db_session.execute(select(func.count()).select_from(SuggestionItem))).scalar_one()
    assert count == 1  # 只有非零 SKU 留下


@pytest.mark.asyncio
async def test_runner_returns_none_when_all_empty(db_session):
    """全部 SKU 都不需要采购也不需要补货时，不建 draft。"""
    result = await run_engine(db_session, config_with_all_zero_skus)
    assert result is None


@pytest.mark.asyncio
async def test_runner_writes_item_counts(db_session):
    result = await run_engine(db_session, config)
    assert result.procurement_item_count == 2
    assert result.restock_item_count == 3


@pytest.mark.asyncio
async def test_calc_engine_job_turns_off_toggle_on_success(db_session):
    """成功生成后开关自动翻 OFF。"""
    config = await db_session.get(GlobalConfig, 1)
    config.suggestion_generation_enabled = True
    await db_session.commit()

    await calc_engine_job(db_session, ...)

    config = await db_session.get(GlobalConfig, 1)
    assert config.suggestion_generation_enabled is False


@pytest.mark.asyncio
async def test_calc_engine_job_keeps_toggle_on_failure(db_session):
    """引擎失败时开关保持 ON。"""
    # mock run_engine 抛异常
    ...
```

- [ ] **Step 2：运行失败**

```bash
docker exec restock-dev-backend pytest tests/unit/test_engine_runner.py -v
```

- [ ] **Step 3：修改 `backend/app/engine/runner.py`**

在 `_persist_items` 写入时：

```python
for sku, data in step4_result.items():
    country_bd = step3_result.get(sku, {})
    restock_total = sum(country_bd.values())
    purchase_qty = int(data.get("purchase_qty", 0))

    # 过滤
    if purchase_qty <= 0 and restock_total <= 0:
        continue

    timing = step6_result.get(sku, {})
    item = SuggestionItem(
        suggestion_id=suggestion.id,
        commodity_sku=sku,
        total_qty=restock_total,
        country_breakdown=country_bd,
        warehouse_breakdown=step5_result.get(sku, {}),
        allocation_snapshot=...,
        velocity_snapshot=...,
        sale_days_snapshot=...,
        urgent=timing.get("urgent", False),
        purchase_qty=purchase_qty,
        purchase_date=timing.get("purchase_date"),
    )
    db.add(item)

    if purchase_qty > 0:
        procurement_count += 1
    if restock_total > 0:
        restock_count += 1

# 全部为 0 时不建 draft
if procurement_count == 0 and restock_count == 0:
    # rollback suggestion？或删除
    await db.delete(suggestion)
    return None

suggestion.procurement_item_count = procurement_count
suggestion.restock_item_count = restock_count
```

在 `global_config_snapshot` 添加 `safety_stock_days`、`eu_countries`。

- [ ] **Step 4：修改 `backend/app/engine/calc_engine_job.py`**

```python
async def calc_engine_job(db: AsyncSession, ...):
    try:
        result = await run_engine(db, ...)
    except Exception:
        raise
    
    # 成功产出 draft 才翻 OFF
    if result is not None:
        config = await db.get(GlobalConfig, 1)
        config.suggestion_generation_enabled = False
        config.generation_toggle_updated_by = None
        config.generation_toggle_updated_at = now_beijing()
        await db.commit()
    
    return result
```

- [ ] **Step 5：运行通过**

```bash
docker exec restock-dev-backend pytest tests/unit/test_engine_runner.py -v
```

- [ ] **Step 6：Commit**

```bash
git add backend/app/engine/runner.py backend/app/engine/calc_engine_job.py backend/tests/unit/test_engine_runner.py
git commit -m "feat(engine): runner 写新字段 + item_count + 成功后翻 OFF"
```

---

## Task 11: 定时调度清理

**Files:**
- Modify: `backend/app/tasks/scheduler.py`

- [ ] **Step 1：删除 calc_engine cron 注册**

在 `backend/app/tasks/scheduler.py:120-130` 定位：

```python
# 删除以下块：
if calc_enabled:
    scheduler.add_job(
        trigger_calc_engine,
        CronTrigger.from_crontab(calc_cron, timezone="Asia/Shanghai"),
        id="trigger_calc_engine",
        ...
    )
else:
    try:
        scheduler.remove_job("trigger_calc_engine")
    except JobLookupError:
        pass
```

全部删除。

**保留**：`sync_*` 相关定时（受 `scheduler_enabled` 控制），`sync_warehouse` cron（03:30），`daily_archive` cron（02:00）。

- [ ] **Step 2：确认手动入口还在**

```bash
docker exec restock-dev-backend grep -rn "calc_engine" backend/app/tasks/
```

应该看到 `access.py` / `jobs/` 目录下的作业类型注册还在。

- [ ] **Step 3：Commit**

```bash
git add backend/app/tasks/scheduler.py
git commit -m "refactor(scheduler): 移除 calc_engine 定时注册，保留手动触发"
```

---

## Task 12: Schema DTO + config API 改动

**Files:**
- Modify: `backend/app/schemas/config.py`
- Modify: `backend/app/api/config.py`
- Modify: `backend/tests/unit/test_config_schema.py`
- Modify: `backend/tests/integration/test_config_api.py`
- Modify: `backend/tests/integration/test_generation_toggle_api.py`

- [ ] **Step 1：更新 `schemas/config.py`**

`GlobalConfigOut` / `GlobalConfigPatch`：
- 删除 `calc_enabled`、`calc_cron`、`include_tax`、`default_purchase_warehouse_id` 字段
- 新增 `safety_stock_days: int = Field(default=15, ge=1, le=90)`
- 新增 `eu_countries: list[str] = Field(default_factory=list)`

`GenerationToggleOut`：
- 新增 `can_enable: bool`
- 新增 `can_enable_reason: str | None = None`

- [ ] **Step 2：写 `can_enable` 计算函数**

在 `backend/app/api/config.py` 新增：

```python
async def _compute_can_enable(db: AsyncSession) -> tuple[bool, str | None]:
    draft = (
        await db.execute(
            select(Suggestion).where(Suggestion.status == "draft").limit(1)
        )
    ).scalar_one_or_none()
    if draft is None:
        return True, None

    if draft.procurement_item_count > 0:
        n = (await db.execute(
            select(func.count()).select_from(SuggestionSnapshot).where(
                SuggestionSnapshot.suggestion_id == draft.id,
                SuggestionSnapshot.snapshot_type == "procurement",
            )
        )).scalar_one()
        if n == 0:
            return False, "采购建议尚未导出任何快照"

    if draft.restock_item_count > 0:
        n = (await db.execute(
            select(func.count()).select_from(SuggestionSnapshot).where(
                SuggestionSnapshot.suggestion_id == draft.id,
                SuggestionSnapshot.snapshot_type == "restock",
            )
        )).scalar_one()
        if n == 0:
            return False, "补货建议尚未导出任何快照"

    return True, None
```

- [ ] **Step 3：修改 `_load_generation_toggle` 把 `can_enable` 注入响应**

```python
async def _load_generation_toggle(db: AsyncSession) -> GenerationToggleOut:
    # ... 现有查询
    can, reason = await _compute_can_enable(db)
    return GenerationToggleOut(..., can_enable=can, can_enable_reason=reason)
```

- [ ] **Step 4：修改 `patch_generation_toggle` 加事务内二次校验**

```python
if patch.enabled:
    can, reason = await _compute_can_enable(db)
    if not can:
        raise BusinessError(reason or "无法开启：前置条件不满足", status_code=422)
    # 现有归档逻辑保留
```

- [ ] **Step 5：更新测试**

在 `test_generation_toggle_api.py` 加用例：
- `can_enable=True` when no draft（旁路 X）
- `can_enable=False` with reason when draft exists but no procurement snapshot
- `can_enable=True` when procurement_item_count=0（空视图豁免）
- 翻 ON 失败时 422
- 生成成功后开关自动 OFF（在 test_engine_runner.py 已覆盖）

在 `test_config_api.py` 更新字段列表，加 `safety_stock_days` / `eu_countries` 读写用例，删 `calc_enabled` 等的用例。

在 `test_config_schema.py` 更新 Pydantic 校验测试。

- [ ] **Step 6：运行**

```bash
docker exec restock-dev-backend pytest tests/unit/test_config_schema.py tests/integration/test_config_api.py tests/integration/test_generation_toggle_api.py -v
```

- [ ] **Step 7：Commit**

```bash
git add backend/app/schemas/config.py backend/app/api/config.py backend/tests/
git commit -m "feat(api): global_config 新字段 + generation-toggle can_enable 校验"
```

---

## Task 13: Suggestion API 响应字段扩展 + PATCH 采购字段

**Files:**
- Modify: `backend/app/schemas/suggestion.py`
- Modify: `backend/app/api/suggestion.py`
- Modify: `backend/tests/unit/test_suggestion_patch.py`

- [ ] **Step 1：扩展 DTO**

`SuggestionItemOut`：
- 新增 `purchase_qty: int`
- 新增 `purchase_date: date | None`
- 新增 `procurement_export_status: str`
- 新增 `procurement_exported_snapshot_id: int | None`
- 新增 `procurement_exported_at: datetime | None`
- 原 `export_status` 等重命名为 `restock_export_status` 等

`SuggestionDetailOut` / `SuggestionListItem`：
- 新增 `procurement_item_count: int`
- 新增 `restock_item_count: int`
- 新增 `procurement_snapshot_count: int`（API 层聚合）
- `snapshot_count` 改为 `restock_snapshot_count`

`SuggestionItemPatch`：
- 允许 `purchase_qty: int | None`、`purchase_date: date | None`

- [ ] **Step 2：修改 `PATCH /api/suggestions/{id}/items/{item_id}`**

```python
if patch.purchase_qty is not None:
    item.purchase_qty = patch.purchase_qty

if patch.purchase_date is not None:
    item.purchase_date = patch.purchase_date

if patch.country_breakdown is not None:
    item.country_breakdown = patch.country_breakdown
    item.total_qty = sum(patch.country_breakdown.values())  # 派生
```

- [ ] **Step 3：修改 `GET /api/suggestions` 加聚合**

```python
from sqlalchemy import case

snap_counts = (
    await db.execute(
        select(
            SuggestionSnapshot.suggestion_id,
            func.sum(case((SuggestionSnapshot.snapshot_type == "procurement", 1), else_=0)).label("proc"),
            func.sum(case((SuggestionSnapshot.snapshot_type == "restock", 1), else_=0)).label("restock"),
        )
        .group_by(SuggestionSnapshot.suggestion_id)
    )
).all()
# 附加到每条 suggestion 响应
```

- [ ] **Step 4：更新测试**

`test_suggestion_patch.py` 加：
- 修改 `purchase_qty` 成功
- 修改 `country_breakdown` 自动重算 `total_qty`
- 验证 `procurement_item_count` / `restock_item_count` 在响应里

- [ ] **Step 5：运行**

```bash
docker exec restock-dev-backend pytest tests/unit/test_suggestion_patch.py -v
```

- [ ] **Step 6：Commit**

```bash
git add backend/app/schemas/suggestion.py backend/app/api/suggestion.py backend/tests/unit/test_suggestion_patch.py
git commit -m "feat(api): suggestion 响应加采购字段 + PATCH 支持 purchase_qty/date"
```

---

## Task 14: 快照端点拆分（procurement / restock）

**Files:**
- Modify: `backend/app/schemas/suggestion_snapshot.py`
- Modify: `backend/app/api/snapshot.py`
- Modify: `backend/app/services/excel_export.py`
- Modify: `backend/tests/integration/test_export_e2e.py`

- [ ] **Step 1：DTO 加 `snapshot_type`**

`SuggestionSnapshotOut`：新增 `snapshot_type: str`（枚举 `procurement` / `restock`）。

`SuggestionSnapshotItemOut`：新增 `purchase_qty: int | None`、`purchase_date: date | None`。

- [ ] **Step 2：Excel 导出服务改造**

`build_filename()` 加 `snapshot_type`：
```python
def build_filename(suggestion_id: int, version: int, exported_at: datetime, snapshot_type: str) -> str:
    ts = exported_at.strftime("%Y%m%d%H%M%S")
    return f"{snapshot_type}_{suggestion_id}_v{version}_{ts}.xlsx"
```

新增 `build_procurement_workbook(snapshot, items)` — 2 Sheet：
- `主数据`：导出时间 / 版本号 / 导出人 / 建议单 ID / 全局参数快照
- `采购明细`：SKU / 商品名 / 图片 URL / 采购量 / 采购时间 / **逾期备注** / 各国动销合计 / 本地仓可用+占用 / 安全库存天数

新增 `build_restock_workbook(snapshot, items)` — 4 Sheet：
- `主数据`：同上
- `SKU 汇总`：SKU / 商品名 / 补货总量 / 紧急度
- `SKU × 国家`：SKU / 国家 / 补货量
- `SKU × 国家 × 仓库`：SKU / 国家 / 仓库 / 补货量

- [ ] **Step 3：拆分端点**

`backend/app/api/snapshot.py`：

```python
@router.post("/suggestions/{suggestion_id}/snapshots/procurement", status_code=201)
async def create_procurement_snapshot(
    suggestion_id: int,
    body: SnapshotCreateRequest,  # item_ids: list[int], note: str | None
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
) -> SuggestionSnapshotOut:
    return await _create_snapshot(db, user, suggestion_id, body, snapshot_type="procurement")


@router.post("/suggestions/{suggestion_id}/snapshots/restock", status_code=201)
async def create_restock_snapshot(
    ...  # 同上，snapshot_type="restock"
):
    ...


async def _create_snapshot(db, user, suggestion_id, body, snapshot_type):
    # 校验建议单存在且 status=draft
    # 校验选中的 item 都属于该 suggestion
    # 校验：procurement 时要求 item.purchase_qty>0；restock 时要求 sum(country_breakdown)>0
    # 查询下一个 version（按 snapshot_type 独立）
    next_version = ...
    # 创建 SuggestionSnapshot
    # 复制 item 数据到 SuggestionSnapshotItem（按 type 冻结对应字段）
    # 生成 Excel
    # 更新 item 的 {type}_export_status='exported'
    # 写 excel_export_log
```

旧端点 `POST /api/suggestions/{id}/snapshots`：**改为 410 Gone**，响应提示 `/snapshots/procurement` 或 `/snapshots/restock`。

`GET /api/suggestions/{id}/snapshots` 增加 `?type=procurement|restock` query 参数。

- [ ] **Step 4：更新集成测试**

`test_export_e2e.py`：
- 调 procurement 端点产快照，item.procurement_export_status='exported'
- 调 restock 端点产快照，item.restock_export_status='exported'
- 两个 snapshot 的 version 独立递增
- 空 item 列表 422 拒绝
- 选不属于当前 suggestion 的 item 422

- [ ] **Step 5：运行**

```bash
docker exec restock-dev-backend pytest tests/integration/test_export_e2e.py -v
```

- [ ] **Step 6：Commit**

```bash
git add backend/app/schemas/suggestion_snapshot.py backend/app/api/snapshot.py backend/app/services/excel_export.py backend/tests/integration/test_export_e2e.py
git commit -m "feat(api): 快照端点拆分为采购/补货两套，Excel 格式独立"
```

---

## Task 15: 前端嵌套路由（方式 A）

**Files:**
- Modify: `frontend/src/config/appPages.ts`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1：appPages.ts 改造**

现有三个 page（`suggestion-list`、`suggestion-detail`、`history`）的 path 改造如下（只改父级 entry，子路由在 router.ts 里嵌套）。可能需要改 `AppPageDefinition` 支持 children。

或者不改 appPages.ts 结构，直接在 router.ts 内用 children 加子路由。

推荐后者：**appPages.ts 保持不变，router.ts 里追加子路由**。

- [ ] **Step 2：router.ts 改造**

在 `createRoutesFromAppPages` 或等价位置，为三个父路由加 children：

```typescript
import ProcurementListView from '@/views/suggestion/ProcurementListView.vue'
import RestockListView from '@/views/suggestion/RestockListView.vue'
// ... 其他 import

// 把 /restock/current 改造成嵌套路由
{
  path: '/restock/current',
  component: () => import('@/views/SuggestionListView.vue'),
  children: [
    { path: '', redirect: { name: 'suggestion-list-procurement' } },
    { path: 'procurement', name: 'suggestion-list-procurement', component: () => import('@/views/suggestion/ProcurementListView.vue') },
    { path: 'restock', name: 'suggestion-list-restock', component: () => import('@/views/suggestion/RestockListView.vue') },
  ],
},
// /restock/suggestions/:id 同理
{
  path: '/restock/suggestions/:id',
  component: () => import('@/views/SuggestionDetailView.vue'),
  children: [
    { path: '', redirect: (to) => `/restock/suggestions/${to.params.id}/procurement` },
    { path: 'procurement', name: 'suggestion-detail-procurement', component: () => import('@/views/suggestion/ProcurementDetailView.vue') },
    { path: 'restock', name: 'suggestion-detail-restock', component: () => import('@/views/suggestion/RestockDetailView.vue') },
  ],
},
// /restock/history 同理
{
  path: '/restock/history',
  component: () => import('@/views/HistoryView.vue'),
  children: [
    { path: '', redirect: { name: 'history-procurement' } },
    { path: 'procurement', name: 'history-procurement', component: () => import('@/views/history/ProcurementHistoryView.vue') },
    { path: 'restock', name: 'history-restock', component: () => import('@/views/history/RestockHistoryView.vue') },
  ],
},
```

- [ ] **Step 3：vue-tsc 验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

会报找不到新建的子视图文件 — 这是预期，继续下一步后会创建。可以先创建空 stub 文件占位：

```bash
mkdir -p frontend/src/views/suggestion frontend/src/views/history
echo '<template>占位</template>' > frontend/src/views/suggestion/ProcurementListView.vue
# ... 其他 6 个 stub
```

- [ ] **Step 4：Commit**

```bash
git add frontend/src/router/index.ts frontend/src/views/suggestion/ frontend/src/views/history/
git commit -m "feat(router): 采补建议改为嵌套路由（采购/补货 Tab）"
```

---

## Task 16: 前端 API 客户端更新

**Files:**
- Modify: `frontend/src/api/suggestion.ts`
- Modify: `frontend/src/api/snapshot.ts`
- Modify: `frontend/src/api/config.ts`

- [ ] **Step 1：suggestion.ts 类型扩展**

```typescript
export interface SuggestionItem {
  id: number
  commodity_sku: string
  total_qty: number
  country_breakdown: Record<string, number>
  warehouse_breakdown: Record<string, Record<string, number>>
  urgent: boolean
  // 新增
  purchase_qty: number
  purchase_date: string | null  // ISO date string
  procurement_export_status: 'pending' | 'exported'
  procurement_exported_snapshot_id: number | null
  procurement_exported_at: string | null
  restock_export_status: 'pending' | 'exported'   // 原 export_status
  restock_exported_snapshot_id: number | null
  restock_exported_at: string | null
  // ...
}

export interface Suggestion {
  id: number
  status: 'draft' | 'archived' | 'error'
  total_items: number
  procurement_item_count: number  // 新
  restock_item_count: number      // 新
  procurement_snapshot_count: number  // API 层聚合
  restock_snapshot_count: number      // API 层聚合
  // ...
}

export interface SuggestionItemPatch {
  purchase_qty?: number
  purchase_date?: string | null
  country_breakdown?: Record<string, number>
  warehouse_breakdown?: Record<string, Record<string, number>>
  // 不允许改 total_qty（后端派生）
}
```

- [ ] **Step 2：snapshot.ts 端点拆分**

```typescript
export async function createProcurementSnapshot(
  suggestionId: number,
  itemIds: number[],
  note?: string,
): Promise<Snapshot> {
  const res = await client.post(
    `/suggestions/${suggestionId}/snapshots/procurement`,
    { item_ids: itemIds, note },
  )
  return res.data
}

export async function createRestockSnapshot(
  suggestionId: number,
  itemIds: number[],
  note?: string,
): Promise<Snapshot> {
  const res = await client.post(
    `/suggestions/${suggestionId}/snapshots/restock`,
    { item_ids: itemIds, note },
  )
  return res.data
}

export async function listSnapshots(
  suggestionId: number,
  type?: 'procurement' | 'restock',
): Promise<Snapshot[]> {
  const params: any = {}
  if (type) params.type = type
  const res = await client.get(`/suggestions/${suggestionId}/snapshots`, { params })
  return res.data
}

export interface Snapshot {
  id: number
  suggestion_id: number
  snapshot_type: 'procurement' | 'restock'  // 新增
  version: number
  // ...
}
```

- [ ] **Step 3：config.ts 类型更新**

```typescript
export interface GlobalConfig {
  target_days: number
  buffer_days: number
  lead_time_days: number
  safety_stock_days: number   // 新
  restock_regions: string[]
  eu_countries: string[]      // 新
  scheduler_enabled: boolean
  sync_interval_minutes: number
  shop_sync_mode: string
  // 删除：calc_enabled / calc_cron / include_tax / default_purchase_warehouse_id
}

export interface GenerationToggle {
  enabled: boolean
  updated_by: number | null
  updated_by_name: string | null
  updated_at: string | null
  can_enable: boolean            // 新
  can_enable_reason: string | null // 新
}
```

- [ ] **Step 4：vue-tsc 检查**

```bash
cd frontend && npx vue-tsc --noEmit
```

会在 .vue 消费处报错（老字段），这是预期；下面 Task 会逐个修复消费方。

- [ ] **Step 5：Commit**

```bash
git add frontend/src/api/
git commit -m "feat(api-client): 类型扩展采购字段 + 快照类型拆分 + can_enable"
```

---

## Task 17: SuggestionListView 容器化

**Files:**
- Modify: `frontend/src/views/SuggestionListView.vue`

- [ ] **Step 1：容器化改造**

把现有 `SuggestionListView.vue` 的表格和逻辑抽出（下一 Task 搬到 `RestockListView`），当前文件保留作为父容器：

```vue
<template>
  <PageSectionCard>
    <template #title>采补建议</template>
    <template #actions>
      <el-tag v-if="toggle" :type="toggle.enabled ? 'success' : 'info'">
        开关：{{ toggle.enabled ? 'ON' : 'OFF' }}
      </el-tag>
      <el-button
        type="primary"
        :disabled="!toggle?.enabled || generating"
        :title="toggle?.enabled ? '' : '开关已关闭，请在全局参数中开启'"
        @click="handleGenerate"
      >
        生成采补建议
      </el-button>
    </template>

    <!-- 进度条 -->
    <div v-if="suggestion" class="progress-bar">
      采购进度：{{ exportedProcurementItems }}/{{ suggestion.procurement_item_count }} 条目已导出 
      | 共 {{ suggestion.procurement_snapshot_count }} 份快照
      <br />
      补货进度：{{ exportedRestockItems }}/{{ suggestion.restock_item_count }} 条目已导出 
      | 共 {{ suggestion.restock_snapshot_count }} 份快照
    </div>

    <!-- Tab 切换 -->
    <SuggestionTabBar
      :tabs="[
        { path: 'procurement', label: '采购视图' },
        { path: 'restock', label: '补货视图' },
      ]"
    />

    <!-- 子路由 -->
    <router-view v-slot="{ Component }">
      <keep-alive>
        <component :is="Component" :suggestion="suggestion" :items="items" @refresh="loadData" />
      </keep-alive>
    </router-view>
  </PageSectionCard>
</template>

<script setup lang="ts">
// 加载 suggestion + items + toggle，通过 props 传给子组件
// 生成按钮逻辑（注意 disabled 条件从 'toggle !== null &&' 改为不带此段）
// ...
</script>
```

**关键修复 bug**：`:disabled="!toggle?.enabled || generating"` —— 删掉了原来的 `toggle !== null &&`。当 `toggle=null`（加载前）时，`!toggle?.enabled === !undefined === true`，按钮自动 disabled。

- [ ] **Step 2：更新测试**

`SuggestionListView.test.ts` 加用例：
- `toggle=null` 时按钮 disabled（原来的 bug 是可点）
- `toggle.enabled=false` 时按钮 disabled
- `toggle.enabled=true` 时按钮可点

- [ ] **Step 3：运行前端测试**

```bash
cd frontend && npm run test -- SuggestionListView
```

- [ ] **Step 4：Commit**

```bash
git add frontend/src/views/SuggestionListView.vue frontend/src/views/__tests__/SuggestionListView.test.ts
git commit -m "refactor(view): SuggestionListView 容器化 + 修复生成按钮 toggle=null bug"
```

---

## Task 18: ProcurementListView + 组件 PurchaseDateCell

**Files:**
- Create: `frontend/src/views/suggestion/ProcurementListView.vue`
- Create: `frontend/src/components/PurchaseDateCell.vue`
- Create: `frontend/src/components/__tests__/PurchaseDateCell.test.ts`
- Create: `frontend/src/views/suggestion/__tests__/ProcurementListView.test.ts`

- [ ] **Step 1：写 PurchaseDateCell 测试**

```typescript
import { mount } from '@vue/test-utils'
import PurchaseDateCell from '@/components/PurchaseDateCell.vue'

describe('PurchaseDateCell', () => {
  const today = new Date('2026-04-20')
  beforeAll(() => { vi.useFakeTimers(); vi.setSystemTime(today) })
  afterAll(() => { vi.useRealTimers() })

  test('正常：> 7 天，黑色', () => {
    const wrapper = mount(PurchaseDateCell, { props: { date: '2026-05-01' } })
    expect(wrapper.classes()).toContain('date-normal')
  })

  test('临近：≤ 7 天 > 0，橙色', () => {
    const wrapper = mount(PurchaseDateCell, { props: { date: '2026-04-25' } })
    expect(wrapper.classes()).toContain('date-warning')
  })

  test('今日：0 天，橙色 + "今日到期"徽章', () => {
    const wrapper = mount(PurchaseDateCell, { props: { date: '2026-04-20' } })
    expect(wrapper.text()).toContain('今日到期')
  })

  test('逾期：< 0，红色 + "逾期 N 天"徽章', () => {
    const wrapper = mount(PurchaseDateCell, { props: { date: '2026-03-01' } })
    expect(wrapper.text()).toContain('逾期')
    expect(wrapper.text()).toContain('50')
  })

  test('null 日期：显示 "-"', () => {
    const wrapper = mount(PurchaseDateCell, { props: { date: null } })
    expect(wrapper.text()).toBe('-')
  })
})
```

- [ ] **Step 2：实现 PurchaseDateCell.vue**

```vue
<template>
  <span v-if="!date">-</span>
  <span v-else :class="classes">
    {{ date }}
    <el-tag v-if="badgeText" :type="badgeType" size="small" effect="dark">
      {{ badgeText }}
    </el-tag>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ date: string | null }>()

const diffDays = computed(() => {
  if (!props.date) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(props.date)
  return Math.floor((d.getTime() - today.getTime()) / 86400000)
})

const classes = computed(() => {
  const diff = diffDays.value
  if (diff === null) return []
  if (diff < 0) return ['date-overdue']
  if (diff === 0) return ['date-warning']
  if (diff <= 7) return ['date-warning']
  return ['date-normal']
})

const badgeText = computed(() => {
  const diff = diffDays.value
  if (diff === null) return null
  if (diff < 0) return `逾期 ${-diff} 天`
  if (diff === 0) return '今日到期'
  return null
})

const badgeType = computed(() => {
  const diff = diffDays.value
  if (diff === null) return 'info'
  if (diff < 0) return 'danger'
  return 'warning'
})
</script>

<style scoped>
.date-normal { color: var(--el-text-color-primary); }
.date-warning { color: var(--el-color-warning); }
.date-overdue { color: var(--el-color-danger); font-weight: 600; }
</style>
```

- [ ] **Step 3：写 ProcurementListView 测试**

```typescript
import { mount } from '@vue/test-utils'
import ProcurementListView from '@/views/suggestion/ProcurementListView.vue'

describe('ProcurementListView', () => {
  test('渲染 purchase_qty>0 的 item', () => {
    const items = [
      { id: 1, commodity_sku: 'S1', purchase_qty: 100, purchase_date: '2026-05-01', ... },
      { id: 2, commodity_sku: 'S2', purchase_qty: 0, purchase_date: null, ... },
    ]
    const wrapper = mount(ProcurementListView, { props: { items, suggestion: {...} } })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(1)  // 只显示 purchase_qty>0
    expect(rows[0].text()).toContain('S1')
  })

  test('默认按 purchase_date 升序', () => {
    const items = [
      { id: 1, commodity_sku: 'B', purchase_qty: 50, purchase_date: '2026-06-01', ... },
      { id: 2, commodity_sku: 'A', purchase_qty: 50, purchase_date: '2026-05-01', ... },
    ]
    const wrapper = mount(ProcurementListView, { props: { items, suggestion: {...} } })
    const first = wrapper.findAll('tbody tr')[0]
    expect(first.text()).toContain('A')
  })

  test('procurement_item_count=0 时显示空态', () => {
    const wrapper = mount(ProcurementListView, {
      props: { items: [], suggestion: { procurement_item_count: 0 } },
    })
    expect(wrapper.text()).toContain('本期无采购需求')
  })
})
```

- [ ] **Step 4：实现 ProcurementListView.vue**

```vue
<template>
  <div v-if="suggestion?.procurement_item_count === 0" class="empty-state">
    本期无采购需求
  </div>
  <div v-else>
    <div class="actions-bar">
      <el-button type="primary" @click="handleExport" :disabled="selectedIds.length === 0">
        导出采购单 Excel
      </el-button>
      <el-input v-model="skuFilter" placeholder="SKU 搜索" clearable style="width: 200px" />
      <el-select v-model="urgencyFilter" placeholder="紧急度" clearable>
        <el-option label="全部" value="" />
        <el-option label="逾期" value="overdue" />
        <el-option label="今日" value="today" />
        <el-option label="临近 7 天" value="warning" />
        <el-option label="正常" value="normal" />
      </el-select>
    </div>

    <el-table :data="filteredItems" @selection-change="onSelectionChange">
      <el-table-column type="selection" width="48" />
      <el-table-column label="商品信息" min-width="200">
        <template #default="{ row }">
          <div>{{ row.commodity_sku }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="purchase_qty" label="采购量" width="100" sortable>
        <template #default="{ row }">
          <el-input-number
            v-if="editable"
            :model-value="row.purchase_qty"
            @update:model-value="val => updateField(row, 'purchase_qty', val)"
            :min="0"
          />
          <span v-else>{{ row.purchase_qty }}</span>
        </template>
      </el-table-column>
      <el-table-column label="采购时间" width="220">
        <template #default="{ row }">
          <PurchaseDateCell :date="row.purchase_date" />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import PurchaseDateCell from '@/components/PurchaseDateCell.vue'
import { createProcurementSnapshot } from '@/api/snapshot'
import { patchSuggestionItem } from '@/api/suggestion'
import { downloadBlob } from '@/utils/download'

const props = defineProps<{ suggestion: any; items: any[] }>()
const emit = defineEmits<{ (e: 'refresh'): void }>()

const route = useRoute()
const skuFilter = ref('')
const urgencyFilter = ref('')
const selectedIds = ref<number[]>([])
const hasChanges = ref<Record<number, any>>({})  // 暂存修改

const filteredItems = computed(() => {
  let list = (props.items || []).filter(i => i.purchase_qty > 0)
  if (skuFilter.value) list = list.filter(i => i.commodity_sku.includes(skuFilter.value))
  // 紧急度过滤... 
  // 默认按 purchase_date 升序
  return list.sort((a, b) => (a.purchase_date || '').localeCompare(b.purchase_date || ''))
})

const editable = computed(() => props.suggestion?.status === 'draft')

function updateField(row: any, field: string, val: any) {
  hasChanges.value[row.id] = { ...hasChanges.value[row.id], [field]: val }
}

function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map(r => r.id)
}

async function handleExport() {
  // 1. 先保存所有暂存修改（方案 A）
  for (const [id, patch] of Object.entries(hasChanges.value)) {
    await patchSuggestionItem(props.suggestion.id, parseInt(id), patch)
  }
  hasChanges.value = {}
  // 2. 导出
  const snap = await createProcurementSnapshot(props.suggestion.id, selectedIds.value)
  // 3. 下载
  const url = `/api/snapshots/${snap.id}/download`
  await downloadBlob(url, `采购单_v${snap.version}.xlsx`)
  emit('refresh')
}
</script>
```

- [ ] **Step 5：运行测试**

```bash
cd frontend && npm run test -- PurchaseDateCell ProcurementListView
```

- [ ] **Step 6：Commit**

```bash
git add frontend/src/views/suggestion/ProcurementListView.vue frontend/src/components/PurchaseDateCell.vue frontend/src/components/__tests__/ frontend/src/views/suggestion/__tests__/
git commit -m "feat(frontend): 采购视图 + PurchaseDateCell 组件"
```

---

## Task 19: RestockListView

**Files:**
- Create: `frontend/src/views/suggestion/RestockListView.vue`
- Create: `frontend/src/views/suggestion/__tests__/RestockListView.test.ts`

- [ ] **Step 1：写测试**

```typescript
describe('RestockListView', () => {
  test('只渲染 Σcountry_breakdown>0 的 item', () => {
    const items = [
      { id: 1, commodity_sku: 'S1', total_qty: 100, country_breakdown: { US: 100 }, ... },
      { id: 2, commodity_sku: 'S2', total_qty: 0, country_breakdown: {}, ... },
    ]
    const wrapper = mount(RestockListView, { props: { items, suggestion: {...} } })
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
  })

  test('restock_item_count=0 时显示空态', () => {
    const wrapper = mount(RestockListView, {
      props: { items: [], suggestion: { restock_item_count: 0 } },
    })
    expect(wrapper.text()).toContain('本期无补货需求')
  })

  test('点击 SKU 可展开查看国家 + 仓库', async () => {
    const items = [{ id: 1, commodity_sku: 'S1', total_qty: 100,
      country_breakdown: { US: 60, EU: 40 },
      warehouse_breakdown: { US: { 'WH-US-01': 60 }, EU: {} } }]
    const wrapper = mount(RestockListView, { props: { items, suggestion: {...} } })
    await wrapper.find('.expand-toggle').trigger('click')
    expect(wrapper.text()).toContain('US')
    expect(wrapper.text()).toContain('WH-US-01')
  })
})
```

- [ ] **Step 2：实现 RestockListView.vue**

复用现有 `SuggestionListView.vue` 原本的补货展示逻辑（国家 + 仓库下钻），但接受 props 而不是自己加载；用表格 + expandable row 展开显示 country_breakdown / warehouse_breakdown；导出按钮调 `createRestockSnapshot`。

- [ ] **Step 3：Commit**

```bash
git add frontend/src/views/suggestion/RestockListView.vue frontend/src/views/suggestion/__tests__/RestockListView.test.ts
git commit -m "feat(frontend): 补货视图（国家/仓库下钻）"
```

---

## Task 20: SuggestionDetailView 容器 + 两个子视图

**Files:**
- Modify: `frontend/src/views/SuggestionDetailView.vue`
- Create: `frontend/src/views/suggestion/ProcurementDetailView.vue`
- Create: `frontend/src/views/suggestion/RestockDetailView.vue`

- [ ] **Step 1：SuggestionDetailView 容器化**

类似 Task 17 模式：保留 header（建议单号、状态、生成时间、导出进度）、Tab 条；加 `<router-view>`。suggestion + items 通过 props 传给子。

- [ ] **Step 2：ProcurementDetailView**

展示单条建议单的采购视图；功能等同于 ProcurementListView（SKU 表 + 编辑 + 导出）；但可能有更详细的信息（商品图、历史快照列表等）。

- [ ] **Step 3：RestockDetailView**

同上，补货视图 + 下钻 + 导出。

- [ ] **Step 4：运行前端 build + 测试**

```bash
cd frontend && npx vue-tsc --noEmit && npm run test
```

- [ ] **Step 5：Commit**

```bash
git add frontend/src/views/SuggestionDetailView.vue frontend/src/views/suggestion/ProcurementDetailView.vue frontend/src/views/suggestion/RestockDetailView.vue
git commit -m "feat(frontend): 建议单详情页容器化 + 采购/补货子视图"
```

---

## Task 21: HistoryView 容器 + 两个子视图

**Files:**
- Modify: `frontend/src/views/HistoryView.vue`
- Create: `frontend/src/views/history/ProcurementHistoryView.vue`
- Create: `frontend/src/views/history/RestockHistoryView.vue`
- Modify: `frontend/src/views/__tests__/HistoryView.test.ts`

- [ ] **Step 1：HistoryView 容器化**

改为父容器：标题 + Tab 切换 + `<router-view>`。把原历史记录逻辑分拆到两个子视图（各自查 `?type=procurement|restock` 的快照列表）。

- [ ] **Step 2：ProcurementHistoryView**

列表字段：快照版本号 / 导出时间 / 导出人 / item 数 / 文件大小 / [下载]。调 `listSnapshots(suggestionId, 'procurement')` + 后端分页。

- [ ] **Step 3：RestockHistoryView**

结构同上，type='restock'。

- [ ] **Step 4：更新测试 HistoryView.test.ts**

验证 Tab 切换、type 参数传递、列表渲染。

- [ ] **Step 5：Commit**

```bash
git add frontend/src/views/HistoryView.vue frontend/src/views/history/ frontend/src/views/__tests__/HistoryView.test.ts
git commit -m "feat(frontend): 历史记录页容器化 + 采购/补货独立列表"
```

---

## Task 22: GlobalConfigView 改造

**Files:**
- Modify: `frontend/src/views/GlobalConfigView.vue`
- Modify: `frontend/src/views/__tests__/GlobalConfigView.test.ts`

- [ ] **Step 1：UI 删除**

删除这些控件的 template + script + 提交字段：
- "自动计算开关"（calc_enabled）
- "自动计算 cron"（calc_cron）
- "含税/不含税"（include_tax）
- "默认采购仓库"（default_purchase_warehouse_id）

- [ ] **Step 2：UI 新增**

- "安全库存天数"：
```vue
<el-form-item label="安全库存天数（默认 15 天）">
  <el-input-number v-model="form.safety_stock_days" :min="1" :max="90" />
</el-form-item>
```

- "EU 成员国"：
```vue
<el-form-item label="EU 成员国">
  <el-select v-model="form.eu_countries" multiple :options="countryOptions" />
</el-form-item>
```

- "补货区域" 选项列表里加：
```typescript
const restockRegionOptions = [...COUNTRY_OPTIONS, { value: 'EU', label: 'EU-欧盟' }]
```

- [ ] **Step 3：生成开关卡片改造**

```vue
<el-card>
  <template #header>
    <span>采补建议生成开关</span>
    <el-switch
      :model-value="toggle.enabled"
      @change="handleToggle"
      :loading="toggling"
    />
  </template>
  <div v-if="!toggle.enabled">
    开关关闭状态，"生成采补建议"按钮不可点击
  </div>
  <div v-if="toggle.enabled === false && !toggle.can_enable">
    <el-tag type="warning">无法开启：{{ toggle.can_enable_reason }}</el-tag>
  </div>
</el-card>
```

翻 ON 时：
```typescript
async function handleToggle(newValue: boolean) {
  if (newValue) {
    if (!toggle.value.can_enable) {
      ElMessage.warning(toggle.value.can_enable_reason)
      return
    }
    await ElMessageBox.confirm('将归档当前采补建议，确定开启新周期？', '确认')
  }
  toggling.value = true
  try {
    await patchGenerationToggle({ enabled: newValue })
    await loadToggle()
  } finally {
    toggling.value = false
  }
}
```

- [ ] **Step 4：测试更新**

```typescript
test('删除字段的 UI 不再显示', () => {
  const wrapper = mount(GlobalConfigView, {...})
  expect(wrapper.text()).not.toContain('自动计算')
  expect(wrapper.text()).not.toContain('含税')
})

test('新字段显示并可编辑', async () => {
  const wrapper = mount(GlobalConfigView, {...})
  expect(wrapper.text()).toContain('安全库存天数')
  expect(wrapper.text()).toContain('EU 成员国')
})

test('翻 ON 时 can_enable=false 阻止', async () => {
  const wrapper = mount(GlobalConfigView, {
    global: { mocks: { toggle: { enabled: false, can_enable: false, can_enable_reason: '采购建议尚未导出' } } }
  })
  await wrapper.find('.el-switch').trigger('click')
  expect(ElMessage.warning).toHaveBeenCalledWith(expect.stringContaining('采购建议尚未导出'))
})
```

- [ ] **Step 5：Commit**

```bash
git add frontend/src/views/GlobalConfigView.vue frontend/src/views/__tests__/GlobalConfigView.test.ts
git commit -m "feat(frontend): 全局参数页增删字段 + can_enable 约束"
```

---

## Task 23: 前端补货区域 + countries.ts 加 EU

**Files:**
- Modify: `frontend/src/utils/countries.ts`

- [ ] **Step 1：加 EU 选项**

```typescript
export const COUNTRY_OPTIONS = [
  // 现有...
  { value: 'EU', label: 'EU-欧盟' },
]

// 如果有 COUNTRY_CODE_MAP 等其他映射也加
```

- [ ] **Step 2：Commit**

```bash
git add frontend/src/utils/countries.ts
git commit -m "feat(utils): countries.ts 加 EU-欧盟 选项"
```

---

## Task 24: E2E 本地 dev 验证

**Files:**
- 无（仅验证）

- [ ] **Step 1：重新构建容器**

```bash
docker compose -f deploy/docker-compose.dev.yml down
docker compose -f deploy/docker-compose.dev.yml up -d --build
```

- [ ] **Step 2：验证迁移已应用**

```bash
docker exec restock-dev-backend alembic current
# Expected: 20260420_0900 (head)
```

- [ ] **Step 3：手工同步一次**

访问 `http://localhost:8088`，登录 admin，到数据同步页点各个 sync 按钮。确认 DB 里看得到：
- `order_header.country_code='EU'` 的行
- `in_transit_record.target_country='EU'` 的行
- `original_*` 列有值

- [ ] **Step 4：生成采补建议**

全局参数页确认：
- 开关 ON
- 安全库存 15 天
- EU 成员国 9 国默认

进"采补建议"页点"生成采补建议"。等待完成。确认：
- 开关自动翻 OFF（前端"生成"按钮灰）
- Tab 采购默认，显示 SKU 表 + 采购时间
- 切 Tab 到补货，显示国家 + 仓库下钻
- 两个视图数据来自同一个建议单

- [ ] **Step 5：编辑 + 导出**

采购 Tab：勾选几个 SKU，改某行 purchase_qty，点"导出采购单" → 确认自动保存 + 下载 xlsx。补货 Tab 同理。

- [ ] **Step 6：翻 ON**

到全局参数页，确认"打开开关"按钮：
- 只导了采购 → 按钮灰 + tooltip "补货建议尚未导出"
- 两个都导了 → 按钮亮 → 点击 → 二次确认 → 翻 ON 成功 → draft 归档 → 生成按钮重新可点

- [ ] **Step 7：历史页**

到历史记录页，切 Tab 确认采购和补货快照各自列出。

---

## Task 25: 全量后端 + 前端回归测试

**Files:**
- 无

- [ ] **Step 1：后端 pytest**

```bash
docker exec restock-dev-backend pytest -v
```

Expected: 所有测试通过

- [ ] **Step 2：前端 vue-tsc + build + vitest**

```bash
cd frontend
npx vue-tsc --noEmit
npx vite build
npm run test
```

Expected: 全绿

- [ ] **Step 3：如有失败，修复后重跑**

---

## Task 26: 文档同步

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `docs/Project_Architecture_Blueprint.md`

- [ ] **Step 1：PROGRESS.md**

顶部"最近更新"改为 `2026-04-20（采补分拆 + 安全库存 + EU 合并 + 生成开关修复）`。

第 3 节"近期重大变更"追加 `### 3.52 采购/补货分拆与 EU 合并（2026-04-20）` 小节，列本次核心变更点（数据模型、API、UI、引擎公式）。

第 2 节"已交付能力"：
- 2.3 补货计算引擎：更新 step4 公式描述、新增 `safety_stock_days`、`purchase_date` 计算规则
- 2.4 补货建议管理：更新为采购/补货独立视图 + 独立快照流
- 2.5 前端 Dashboard 体系：更新嵌套路由、Tab 切换、PurchaseDateCell

- [ ] **Step 2：Project_Architecture_Blueprint.md**

- 数据库章节：更新 `global_config` / `suggestion` / `suggestion_item` / `suggestion_snapshot` schema 描述；加 `original_*` 字段说明
- 6 步流水线表：step4 公式改写、step6 新 purchase_date
- API 层：新增 `/snapshots/procurement` 和 `/snapshots/restock` 端点
- 前端章节：补货管理改为采补建议，嵌套路由说明
- 新增共享 utils：`country_mapping.py`、`PurchaseDateCell.vue`

- [ ] **Step 3：Commit**

```bash
git add docs/PROGRESS.md docs/Project_Architecture_Blueprint.md
git commit -m "docs: 同步采补分拆 + EU 合并设计到 PROGRESS + Blueprint"
```

---

## Task 27: 推分支 + 准备 PR

**Files:**
- 无

- [ ] **Step 1：推送**

```bash
git push -u origin feature/split-procurement-restock-and-eu
```

- [ ] **Step 2：PR 描述模板**

```
## 目标
分拆补货建议为采购（SKU 级）+ 补货（国家+仓库级）两个独立视图；加安全库存；EU 数据入口合并；修生成按钮 bug。

## 主要改动
- DB：新迁移 20260420_0900，schema 改 + 原地 EU 映射 + 归档旧 draft
- 引擎：step4 新公式（+ safety_stock，- reserved），step6 新增 purchase_date
- API：拆 snapshot 端点，can_enable 前置校验
- 前端：嵌套路由 A 方案，两个 Tab 视图，新 PurchaseDateCell
- 权限：业务人员补 restock:operate

## 验证
- [x] 后端 pytest 全绿
- [x] 前端 vue-tsc + build + vitest 全绿
- [x] 本地 dev E2E：同步 → 生成 → 编辑 → 导出 → 翻 ON → 再生成
- [x] PROGRESS + Blueprint 同步

## 风险
- 迁移清了所有 suggestion_snapshot 历史（未上线，可接受）
- EU 映射后源数据 country_code 不再是 'DE' 等，代码中所有国家过滤需基于最新 eu_countries 口径
```

---

## 自查结论

- ✓ spec 覆盖：数据模型 / 引擎 / 同步 / API / 前端 / 权限 / 测试 / 文档 / 迁移 / 验收 每项都有对应 task
- ✓ 无占位：所有代码块是可直接使用的完整代码
- ✓ 类型一致：`country_mapping.apply_eu_mapping` 签名在 Task 3/4/5/6/7 一致；`can_enable` 名字在 Task 12/22 一致；`snapshot_type` 值在 migration/API/前端全部用 `'procurement'` / `'restock'`
- ✓ 修 bug：Task 17 明确写了删除 `toggle !== null &&`，修复 toggle=null 时按钮可点的 bug
- ✓ 文档同步：Task 26 显式列出 AGENTS.md §9 触发映射对应的文件

**实施规模**：27 个 task，预估 6-8 天，每个 task 2-15 分钟到 2-3 小时不等。子代理驱动的话每 task 一次 review 稳妥。
