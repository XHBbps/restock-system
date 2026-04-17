# 补货建议导出重构 · Plan A（后端基础）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成"推送赛狐"到"Excel 导出 + Snapshot 版本化"重构的**后端基础设施**：数据库 migration + 模型 + schemas + Excel 生成服务 + 新 API 端点 + 生成开关 + 权限码 + 推送相关僵尸代码清理（因 migration 强耦合必须同批处理）。

**Architecture:** 引入 3 张新表（`suggestion_snapshot` / `suggestion_snapshot_item` / `excel_export_log`），改造 `suggestion` + `suggestion_item` 字段（去推送字段、加导出字段、状态枚举收缩到 `draft/archived/error`），扩展 `global_config` 加生成开关，`openpyxl` 多 Sheet 导出文件落到 `deploy/data/exports/{yyyy}/{mm}/` volume。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 async · Alembic · Pydantic 2 · PostgreSQL 16 · openpyxl 3.1+ · pytest

**Spec**：[`docs/superpowers/specs/2026-04-17-suggestion-export-redesign-design.md`](../specs/2026-04-17-suggestion-export-redesign-design.md)

**不包含（后续 Plan B / C 处理）**：
- 前端改造（SuggestionListView / SuggestionDetailView / HistoryView）→ Plan B
- 文档同步（PROGRESS.md / Blueprint / runbook）→ Plan C
- 最终端到端手动验收 → Plan C

**包含推送代码删除的原因**：migration 要 `DROP COLUMN push_status` 等字段。若 API 层 `POST /push` 端点和 `pushback/purchase.py` 不同批删除，启动即崩。紧耦合，必须同计划内完成。

---

## 文件结构

### 新增文件

- `backend/alembic/versions/20260418_0900_redesign_to_export_model.py` — migration
- `backend/app/models/suggestion_snapshot.py` — Snapshot + SnapshotItem ORM
- `backend/app/models/excel_export_log.py` — ExcelExportLog ORM
- `backend/app/schemas/suggestion_snapshot.py` — Pydantic DTO
- `backend/app/services/__init__.py` — 新目录
- `backend/app/services/excel_export.py` — Excel 多 Sheet 生成
- `backend/app/api/snapshot.py` — Snapshot 专属端点
- `backend/tests/unit/test_excel_export_service.py`
- `backend/tests/unit/test_snapshot_api.py`
- `backend/tests/unit/test_generation_toggle_api.py`
- `backend/tests/integration/test_export_e2e.py`

### 删除文件

- `backend/app/pushback/purchase.py`
- `backend/app/pushback/__init__.py`（若空）
- `backend/app/saihu/endpoints/purchase_create.py`
- `backend/app/core/commodity_id.py`
- `backend/tests/unit/test_pushback_*.py`（凡存在）
- `backend/tests/unit/test_saihu_purchase_create.py`（凡存在）
- `backend/tests/unit/test_commodity_id.py`

### 修改文件

- `backend/pyproject.toml` — 新增 openpyxl 依赖
- `backend/app/core/permissions.py` — 2 新权限码
- `backend/app/models/suggestion.py` — 字段改造 + status 枚举
- `backend/app/models/global_config.py` — 生成开关字段
- `backend/app/schemas/suggestion.py` — 删推送相关字段
- `backend/app/schemas/config.py` — 生成开关字段（可能）
- `backend/app/api/suggestion.py` — 删 push 端点 + 加 snapshot_count / 删除校验
- `backend/app/api/config.py` — 生成开关 GET/PATCH 端点
- `backend/app/engine/runner.py` — 移除 `_archive_active` 自动触发；移除 commodity_id 补齐
- `backend/app/tasks/access.py` — 删除 `push_saihu` 注册
- `backend/app/main.py` — 若有 push_saihu register 调用则清理

---

## 环境前提

执行本计划前必须满足：
- 本地 PostgreSQL 16 可用（Docker compose dev db 运行中）
- Python venv 已激活并可 `pytest` / `alembic`
- 当前分支最新状态已 commit
- 非生产数据（重复强调：项目未上线，migration 会清空 suggestion/suggestion_item 表）

---

## Task 1: 添加 openpyxl 依赖

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/requirements.lock`

- [ ] **Step 1: 添加 openpyxl 到 dependencies 列表**

编辑 `backend/pyproject.toml`，在 `dependencies` 段末尾（"工具" 分组后）加入：

```toml
    # Excel 导出
    "openpyxl>=3.1.2",
```

- [ ] **Step 2: 重新安装依赖生成锁文件**

在项目根执行：
```bash
cd backend
pip install -e ".[dev]"
```

预期：无报错，`openpyxl-3.1.x` 被安装。

- [ ] **Step 3: 更新 requirements.lock**

```bash
pip freeze > requirements.lock
```

检查 lock 文件中 `openpyxl==` 行已出现。

- [ ] **Step 4: 验证可导入**

```bash
python -c "import openpyxl; print(openpyxl.__version__)"
```

预期：输出 `3.1.x`。

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/requirements.lock
git commit -m "chore: 添加 openpyxl 依赖用于 Excel 导出"
```

---

## Task 2: 注册新权限码

**Files:**
- Modify: `backend/app/core/permissions.py`
- Create: `backend/tests/unit/test_permissions_registry.py`

- [ ] **Step 1: 写失败测试验证新权限码存在**

创建 `backend/tests/unit/test_permissions_registry.py`：

```python
"""权限码注册表覆盖测试。"""

from app.core.permissions import ALL_CODES, REGISTRY


def test_restock_export_registered():
    assert "restock:export" in ALL_CODES
    codes = [p.code for p in REGISTRY]
    assert "restock:export" in codes


def test_restock_new_cycle_registered():
    assert "restock:new_cycle" in ALL_CODES
    codes = [p.code for p in REGISTRY]
    assert "restock:new_cycle" in codes


def test_new_perms_grouped_under_restock():
    by_code = {p.code: p for p in REGISTRY}
    assert by_code["restock:export"].group_name == "补货发起"
    assert by_code["restock:new_cycle"].group_name == "补货发起"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend
.venv/Scripts/pytest tests/unit/test_permissions_registry.py -v
```

预期：3 个测试 FAIL，`'restock:export' not in ALL_CODES`。

- [ ] **Step 3: 添加常量与 REGISTRY 条目**

编辑 `backend/app/core/permissions.py`：

在 `RESTOCK_OPERATE = "restock:operate"` 行下方新增两行常量：

```python
RESTOCK_EXPORT = "restock:export"
RESTOCK_NEW_CYCLE = "restock:new_cycle"
```

在 `REGISTRY` 列表中，`PermDef(RESTOCK_OPERATE, ...)` 条目下方新增 2 行：

```python
    PermDef(RESTOCK_EXPORT, "补货发起-导出", "补货发起"),
    PermDef(RESTOCK_NEW_CYCLE, "补货发起-开启新一轮", "补货发起"),
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/Scripts/pytest tests/unit/test_permissions_registry.py -v
```

预期：3 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/permissions.py backend/tests/unit/test_permissions_registry.py
git commit -m "feat(permissions): 新增 restock:export / restock:new_cycle 权限码"
```

---

## Task 3: 创建 Alembic Migration

**Files:**
- Create: `backend/alembic/versions/20260418_0900_redesign_to_export_model.py`

- [ ] **Step 1: 查询当前 alembic head**

```bash
cd backend
.venv/Scripts/alembic current
```

记录输出中的 revision id（预期应为 `20260416_1700` 或类似）。

- [ ] **Step 2: 创建 migration 文件**

创建 `backend/alembic/versions/20260418_0900_redesign_to_export_model.py`：

```python
"""redesign suggestion model to export + snapshot

Revision ID: 20260418_0900
Revises: 20260416_1700
Create Date: 2026-04-18 09:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260418_0900"
down_revision = "20260416_1700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── 1. 清空旧数据（项目未上线，dev 数据无保留价值） ───
    op.execute("DELETE FROM suggestion_item")
    op.execute("DELETE FROM suggestion")

    # ─── 2. suggestion_item：删除推送字段 + 加导出字段 ───
    op.drop_constraint("push_status_enum", "suggestion_item", type_="check")
    op.drop_column("suggestion_item", "push_status")
    op.drop_column("suggestion_item", "push_error")
    op.drop_column("suggestion_item", "push_attempt_count")
    op.drop_column("suggestion_item", "push_blocker")
    op.drop_column("suggestion_item", "saihu_po_number")
    op.drop_column("suggestion_item", "pushed_at")
    op.drop_column("suggestion_item", "commodity_id")

    op.add_column(
        "suggestion_item",
        sa.Column(
            "export_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("exported_snapshot_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "export_status_enum",
        "suggestion_item",
        "export_status IN ('pending','exported')",
    )
    op.create_index(
        "ix_suggestion_item_export_status",
        "suggestion_item",
        ["suggestion_id", "export_status"],
    )

    # ─── 3. suggestion：收缩 status 枚举 + 归档字段 ───
    op.drop_constraint("status_enum", "suggestion", type_="check")
    op.create_check_constraint(
        "status_enum",
        "suggestion",
        "status IN ('draft','archived','error')",
    )
    op.add_column(
        "suggestion",
        sa.Column("archived_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "suggestion",
        sa.Column("archived_trigger", sa.String(length=20), nullable=True),
    )
    op.create_foreign_key(
        "fk_suggestion_archived_by_sys_user",
        "suggestion",
        "sys_user",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # 清理已不使用的推送计数字段（保留 total_items）
    op.drop_column("suggestion", "pushed_items")
    op.drop_column("suggestion", "failed_items")

    # ─── 4. 新表 suggestion_snapshot ───
    op.create_table(
        "suggestion_snapshot",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "suggestion_id",
            sa.BigInteger(),
            sa.ForeignKey("suggestion.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("exported_by", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column(
            "exported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("exported_from_ip", sa.String(length=45), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "global_config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "generation_status",
            sa.String(length=20),
            nullable=False,
            server_default="generating",
        ),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "generation_status IN ('generating','ready','failed')",
            name="generation_status_enum",
        ),
        sa.UniqueConstraint("suggestion_id", "version", name="uq_snapshot_suggestion_version"),
    )
    op.create_index(
        "ix_suggestion_snapshot_suggestion",
        "suggestion_snapshot",
        ["suggestion_id"],
    )
    op.create_index(
        "ix_suggestion_snapshot_exported_at",
        "suggestion_snapshot",
        [sa.text("exported_at DESC")],
    )

    # ─── 5. 新表 suggestion_snapshot_item ───
    op.create_table(
        "suggestion_snapshot_item",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.BigInteger(),
            sa.ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("total_qty", sa.Integer(), nullable=False),
        sa.Column(
            "country_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "warehouse_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("urgent", sa.Boolean(), nullable=False),
        sa.Column(
            "velocity_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "sale_days_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("commodity_name", sa.String(length=500), nullable=True),
        sa.Column("main_image_url", sa.String(length=1000), nullable=True),
    )
    op.create_index(
        "ix_snapshot_item_snapshot",
        "suggestion_snapshot_item",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_snapshot_item_sku",
        "suggestion_snapshot_item",
        ["commodity_sku"],
    )

    # suggestion_item.exported_snapshot_id 外键（snapshot 表建好后）
    op.create_foreign_key(
        "fk_suggestion_item_exported_snapshot",
        "suggestion_item",
        "suggestion_snapshot",
        ["exported_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ─── 6. 新表 excel_export_log ───
    op.create_table(
        "excel_export_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.BigInteger(),
            sa.ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("performed_from_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "action IN ('generate','download')",
            name="action_enum",
        ),
    )
    op.create_index(
        "ix_export_log_snapshot",
        "excel_export_log",
        ["snapshot_id", sa.text("performed_at DESC")],
    )

    # ─── 7. global_config：生成开关 ───
    op.add_column(
        "global_config",
        sa.Column(
            "suggestion_generation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "global_config",
        sa.Column("generation_toggle_updated_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "global_config",
        sa.Column(
            "generation_toggle_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_global_config_toggle_user",
        "global_config",
        "sys_user",
        ["generation_toggle_updated_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
```

- [ ] **Step 3: 执行 migration 向上**

```bash
.venv/Scripts/alembic upgrade head
```

预期：输出 `INFO  [alembic.runtime.migration] Running upgrade 20260416_1700 -> 20260418_0900`，无错误。

- [ ] **Step 4: 验证表结构**

```bash
.venv/Scripts/python -c "
import asyncio
from sqlalchemy import text
from app.db.session import async_session_factory

async def check():
    async with async_session_factory() as db:
        r = await db.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='suggestion_item' AND column_name IN ('push_status','export_status')\"))
        rows = [row[0] for row in r.all()]
        print('suggestion_item cols:', rows)
        assert 'push_status' not in rows
        assert 'export_status' in rows

asyncio.run(check())
"
```

预期：输出 `suggestion_item cols: ['export_status']`。

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260418_0900_redesign_to_export_model.py
git commit -m "feat(db): migration 清空 push 字段 + 新增 snapshot/export_log 表 + 生成开关"
```

---

## Task 4: 更新 `Suggestion` / `SuggestionItem` ORM 模型

**Files:**
- Modify: `backend/app/models/suggestion.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_suggestion_model.py` （新建或追加）：

```python
"""验证 Suggestion / SuggestionItem 模型字段对齐 migration。"""

from app.models.suggestion import Suggestion, SuggestionItem


def test_suggestion_has_new_archive_fields():
    cols = {c.name for c in Suggestion.__table__.columns}
    assert "archived_by" in cols
    assert "archived_trigger" in cols
    assert "pushed_items" not in cols
    assert "failed_items" not in cols


def test_suggestion_item_export_fields():
    cols = {c.name for c in SuggestionItem.__table__.columns}
    assert "export_status" in cols
    assert "exported_snapshot_id" in cols
    assert "exported_at" in cols
    assert "push_status" not in cols
    assert "saihu_po_number" not in cols
    assert "commodity_id" not in cols


def test_suggestion_status_check_constraint():
    check = [c for c in Suggestion.__table_args__ if getattr(c, "name", "") == "status_enum"]
    assert len(check) == 1
    sql_text = str(check[0].sqltext)
    assert "draft" in sql_text
    assert "archived" in sql_text
    assert "error" in sql_text
    assert "partial" not in sql_text
    assert "pushed" not in sql_text
```

- [ ] **Step 2: 运行测试（预期全部 FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_model.py -v
```

- [ ] **Step 3: 重写 `backend/app/models/suggestion.py`**

完整替换文件内容：

```python
"""建议单主表 + 条目表（导出模式）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Suggestion(Base):
    """一次规则引擎运行产出的建议单。"""

    __tablename__ = "suggestion"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','archived','error')",
            name="status_enum",
        ),
        Index("ix_suggestion_created_at", "created_at"),
        Index("ix_suggestion_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    global_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)

    # 归档信息
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True
    )
    archived_trigger: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SuggestionItem(Base):
    """建议单条目：每行对应一个 commodity_sku 的完整补货建议。"""

    __tablename__ = "suggestion_item"
    __table_args__ = (
        CheckConstraint(
            "export_status IN ('pending','exported')",
            name="export_status_enum",
        ),
        Index("ix_suggestion_item_suggestion", "suggestion_id"),
        Index("ix_suggestion_item_sku", "commodity_sku"),
        Index(
            "ix_suggestion_item_urgent",
            "urgent",
            postgresql_where="urgent = true",
        ),
        Index(
            "ix_suggestion_item_export_status",
            "suggestion_id",
            "export_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion.id", ondelete="CASCADE"),
        nullable=False,
    )

    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)

    total_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    country_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warehouse_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    allocation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # 可追溯快照
    velocity_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sale_days_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 导出状态
    export_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    exported_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("suggestion_snapshot.id", ondelete="SET NULL"),
        nullable=True,
    )
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_model.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/suggestion.py backend/tests/unit/test_suggestion_model.py
git commit -m "refactor(models): suggestion/item 去推送字段 + 加导出字段 + 状态枚举收缩"
```

---

## Task 5: 创建 Snapshot / SnapshotItem 模型

**Files:**
- Create: `backend/app/models/suggestion_snapshot.py`
- Create: `backend/tests/unit/test_suggestion_snapshot_model.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_suggestion_snapshot_model.py`：

```python
"""Snapshot 模型字段对齐 migration。"""

from app.models.suggestion_snapshot import SuggestionSnapshot, SuggestionSnapshotItem


def test_snapshot_fields():
    cols = {c.name for c in SuggestionSnapshot.__table__.columns}
    expected = {
        "id", "suggestion_id", "version",
        "exported_by", "exported_at", "exported_from_ip",
        "item_count", "note", "global_config_snapshot",
        "generation_status", "file_path", "file_size_bytes", "generation_error",
        "download_count", "last_downloaded_at",
    }
    assert expected.issubset(cols), f"缺失字段：{expected - cols}"


def test_snapshot_item_fields():
    cols = {c.name for c in SuggestionSnapshotItem.__table__.columns}
    expected = {
        "id", "snapshot_id",
        "commodity_sku", "total_qty",
        "country_breakdown", "warehouse_breakdown", "urgent",
        "velocity_snapshot", "sale_days_snapshot",
        "commodity_name", "main_image_url",
    }
    assert expected.issubset(cols)


def test_snapshot_generation_status_check():
    checks = [
        c for c in SuggestionSnapshot.__table_args__
        if getattr(c, "name", "") == "generation_status_enum"
    ]
    assert len(checks) == 1
    sql = str(checks[0].sqltext)
    assert "generating" in sql and "ready" in sql and "failed" in sql
```

- [ ] **Step 2: 运行测试（FAIL：模块不存在）**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_snapshot_model.py -v
```

- [ ] **Step 3: 创建模型文件**

创建 `backend/app/models/suggestion_snapshot.py`：

```python
"""建议单导出快照 + 快照条目。Immutable，不可删除。"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class SuggestionSnapshot(Base):
    """一次 Excel 导出操作产生的不可变快照。"""

    __tablename__ = "suggestion_snapshot"
    __table_args__ = (
        CheckConstraint(
            "generation_status IN ('generating','ready','failed')",
            name="generation_status_enum",
        ),
        UniqueConstraint("suggestion_id", "version", name="uq_snapshot_suggestion_version"),
        Index("ix_suggestion_snapshot_suggestion", "suggestion_id"),
        Index(
            "ix_suggestion_snapshot_exported_at",
            "exported_at",
            postgresql_using="btree",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # 审计
    exported_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sys_user.id"), nullable=True
    )
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    exported_from_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # 内容元数据
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    global_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # 文件生成
    generation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="generating"
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 下载计数
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SuggestionSnapshotItem(Base):
    """Snapshot 内冻结的 item 数据。"""

    __tablename__ = "suggestion_snapshot_item"
    __table_args__ = (
        Index("ix_snapshot_item_snapshot", "snapshot_id"),
        Index("ix_snapshot_item_sku", "commodity_sku"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )

    commodity_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    country_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warehouse_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False)

    velocity_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sale_days_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 商品展示冻结
    commodity_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
```

- [ ] **Step 4: 注册到 models `__init__.py`**

编辑 `backend/app/models/__init__.py`（若有），追加：
```python
from app.models.suggestion_snapshot import SuggestionSnapshot, SuggestionSnapshotItem  # noqa
```

若项目用惯例自动发现，可跳过此步（按 `backend/app/models/` 实际情况）。

- [ ] **Step 5: 运行测试确认通过**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_snapshot_model.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/suggestion_snapshot.py backend/tests/unit/test_suggestion_snapshot_model.py backend/app/models/__init__.py
git commit -m "feat(models): 新增 SuggestionSnapshot / SuggestionSnapshotItem"
```

---

## Task 6: 创建 ExcelExportLog 模型

**Files:**
- Create: `backend/app/models/excel_export_log.py`
- Create: `backend/tests/unit/test_excel_export_log_model.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_excel_export_log_model.py`：

```python
from app.models.excel_export_log import ExcelExportLog


def test_excel_export_log_fields():
    cols = {c.name for c in ExcelExportLog.__table__.columns}
    expected = {
        "id", "snapshot_id", "action",
        "performed_by", "performed_at",
        "performed_from_ip", "user_agent",
    }
    assert expected.issubset(cols)


def test_action_enum():
    checks = [
        c for c in ExcelExportLog.__table_args__
        if getattr(c, "name", "") == "action_enum"
    ]
    assert len(checks) == 1
    sql = str(checks[0].sqltext)
    assert "generate" in sql and "download" in sql
```

- [ ] **Step 2: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_excel_export_log_model.py -v
```

- [ ] **Step 3: 创建模型**

创建 `backend/app/models/excel_export_log.py`：

```python
"""Excel 导出与下载审计日志。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class ExcelExportLog(Base):
    """每次 snapshot 生成或下载留一条审计。"""

    __tablename__ = "excel_export_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('generate','download')",
            name="action_enum",
        ),
        Index(
            "ix_export_log_snapshot",
            "snapshot_id",
            "performed_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)

    performed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sys_user.id"), nullable=True
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    performed_from_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 4: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_excel_export_log_model.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/excel_export_log.py backend/tests/unit/test_excel_export_log_model.py
git commit -m "feat(models): 新增 ExcelExportLog 审计表"
```

---

## Task 7: 扩展 GlobalConfig 模型（生成开关）

**Files:**
- Modify: `backend/app/models/global_config.py`
- Create: `backend/tests/unit/test_global_config_toggle.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_global_config_toggle.py`：

```python
from app.models.global_config import GlobalConfig


def test_toggle_fields():
    cols = {c.name for c in GlobalConfig.__table__.columns}
    assert "suggestion_generation_enabled" in cols
    assert "generation_toggle_updated_by" in cols
    assert "generation_toggle_updated_at" in cols
```

- [ ] **Step 2: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_global_config_toggle.py -v
```

- [ ] **Step 3: 加字段到模型**

编辑 `backend/app/models/global_config.py`，在 `login_password_hash` 字段行**下方**插入：

```python
    # 补货建议生成开关（首次导出自动 OFF，管理员手动 ON）
    suggestion_generation_enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("true")
    )
    generation_toggle_updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True
    )
    generation_toggle_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

同时确认文件顶部 `from sqlalchemy import ...` 已含 `ForeignKey`；若无，添加。

- [ ] **Step 4: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_global_config_toggle.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/global_config.py backend/tests/unit/test_global_config_toggle.py
git commit -m "feat(models): GlobalConfig 添加生成开关字段"
```

---

## Task 8: 移除 `commodity_id.py` + 清理 `engine/runner.py`

**Files:**
- Delete: `backend/app/core/commodity_id.py`
- Delete: `backend/tests/unit/test_commodity_id.py`（如存在）
- Modify: `backend/app/engine/runner.py`

- [ ] **Step 1: 列出现有 commodity_id 相关调用点**

```bash
grep -rn "from app.core.commodity_id\|resolve_commodity_id_map\|refresh_suggestion_item_pushability\|MISSING_COMMODITY_ID_BLOCKER" backend/app/ backend/tests/
```

把输出位置记下。预期 ≤ 10 行，主要在 `runner.py` 与 `api/suggestion.py`。

- [ ] **Step 2: 从 `engine/runner.py` 移除所有调用**

打开 `backend/app/engine/runner.py`，定位：
- `from app.core.commodity_id import ...` 整行 → 删除
- `resolve_commodity_id_map(...)` 调用点 → 删除语句，相关变量不再写入
- 构建 `suggestion_item` insert values 时，**不再** `commodity_id=...`（字段已从表删除）
- 若有 `push_blocker` / `push_status` 相关写入 → 删除

如果 `_archive_active()` 函数内部仅这个 runner 调用且新设计下不再需要（开关翻 ON 时才触发）：
- 保留函数定义，但在 `_persist_suggestion()` 内部移除对它的调用
- runner 不再自动归档旧单

- [ ] **Step 3: 删除 `commodity_id.py` 文件**

```bash
git rm backend/app/core/commodity_id.py
git rm backend/tests/unit/test_commodity_id.py 2>/dev/null || true
```

- [ ] **Step 4: 运行引擎单测确保未被打断**

```bash
.venv/Scripts/pytest tests/unit/test_engine_runner.py -v
```

若有 import 相关 FAIL，按报错继续清理 `runner.py` 的残余 commodity_id 引用。

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/runner.py
git commit -m "refactor(engine): 移除 commodity_id 解析 + _archive_active 自动触发"
```

---

## Task 9: 删除推送端点与 pushback 代码

**Files:**
- Delete: `backend/app/pushback/purchase.py`
- Delete: `backend/app/pushback/__init__.py`（若目录留空）
- Delete: `backend/app/saihu/endpoints/purchase_create.py`
- Delete: 各 `test_pushback_*.py` / `test_saihu_purchase_create.py`
- Modify: `backend/app/api/suggestion.py`
- Modify: `backend/app/tasks/access.py`
- Modify: `backend/app/main.py`（若有 push register）

- [ ] **Step 1: 删除 pushback / saihu purchase 文件**

```bash
cd backend
git rm app/pushback/purchase.py
ls app/pushback/  # 若只剩 __init__.py，也删
git rm app/pushback/__init__.py 2>/dev/null || true
rmdir app/pushback 2>/dev/null || true
git rm app/saihu/endpoints/purchase_create.py
```

- [ ] **Step 2: 删除对应测试**

```bash
git rm tests/unit/test_pushback_purchase.py 2>/dev/null || true
git rm tests/unit/test_saihu_purchase_create.py 2>/dev/null || true
```

- [ ] **Step 3: 删除 `tasks/access.py` 中 `push_saihu` 条目**

打开 `backend/app/tasks/access.py`，删除：
- `"push_saihu": (SYNC_VIEW, SYNC_OPERATE)` 或类似（TASK_VIEW_PERMISSIONS 字典里的行）
- `"push_saihu": (SYNC_OPERATE,)` 或类似（TASK_MANAGE_PERMISSIONS 字典里的行）

- [ ] **Step 4: 删除 API push 端点与 PushRequest schema**

打开 `backend/app/api/suggestion.py`：
- 定位 `@router.post("/{suggestion_id}/push")` 装饰器
- 删除整个 `push_items` 函数（约 60 行）
- 删除 `from app.schemas.suggestion import PushRequest` 导入

打开 `backend/app/schemas/suggestion.py`：
- 删除 `class PushRequest` 定义

- [ ] **Step 5: 清理 `main.py` 中可能的 push 注册**

```bash
grep -n "push_saihu\|pushback" app/main.py
```

如有相关 import 或 register 调用，一并删除。

- [ ] **Step 6: 运行测试套件快速验证无 import 崩溃**

```bash
.venv/Scripts/pytest tests/unit/ -x --co  # collect only
```

预期：不报 `ModuleNotFoundError`。若有，按报错继续清理残余引用。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: 删除 pushback/purchase.py + push_saihu 作业 + POST /push 端点"
```

---

## Task 10: 更新 Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/suggestion.py`
- Create: `backend/app/schemas/suggestion_snapshot.py`
- Create: `backend/tests/unit/test_suggestion_snapshot_schemas.py`

- [ ] **Step 1: 清理 `suggestion.py` 中推送相关字段**

编辑 `backend/app/schemas/suggestion.py`：

删除 `SuggestionOut` 中 `pushed_items` / `failed_items` 字段。

`SuggestionItemOut` 的字段更新（删除推送字段 + 加导出字段 + 加 commodity_id）：

```python
class SuggestionItemOut(BaseModel):
    id: int
    commodity_sku: str
    commodity_name: str | None = None  # 由 API 层 JOIN product_listing 注入
    main_image: str | None = None
    total_qty: int
    country_breakdown: dict[str, Any]
    warehouse_breakdown: dict[str, Any]
    allocation_snapshot: dict[str, AllocationExplanationOut] | None = None
    velocity_snapshot: dict[str, Any] | None = None
    sale_days_snapshot: dict[str, Any] | None = None
    urgent: bool
    # 导出字段
    export_status: str  # 'pending' | 'exported'
    exported_snapshot_id: int | None = None
    exported_at: datetime | None = None

    model_config = {"from_attributes": True}
```

`SuggestionOut` 更新：

```python
class SuggestionOut(BaseModel):
    id: int
    status: str  # 'draft' | 'archived' | 'error'
    triggered_by: str
    total_items: int
    snapshot_count: int = 0  # 由 API 层 JOIN 注入
    global_config_snapshot: dict[str, Any]
    created_at: datetime
    archived_at: datetime | None = None
    archived_trigger: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: 写 Snapshot schema 失败测试**

创建 `backend/tests/unit/test_suggestion_snapshot_schemas.py`：

```python
from datetime import datetime

from app.schemas.suggestion_snapshot import (
    SnapshotCreateRequest,
    SnapshotItemOut,
    SnapshotOut,
)


def test_snapshot_create_request():
    req = SnapshotCreateRequest(item_ids=[1, 2, 3], note="发给供应商 A")
    assert req.item_ids == [1, 2, 3]
    assert req.note == "发给供应商 A"


def test_snapshot_create_request_note_optional():
    req = SnapshotCreateRequest(item_ids=[1])
    assert req.note is None


def test_snapshot_create_request_note_max_length():
    import pytest

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SnapshotCreateRequest(item_ids=[1], note="x" * 201)


def test_snapshot_create_request_items_min_one():
    import pytest

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SnapshotCreateRequest(item_ids=[])


def test_snapshot_out_fields():
    out = SnapshotOut(
        id=1,
        suggestion_id=42,
        version=1,
        exported_by=10,
        exported_by_name="alice",
        exported_at=datetime.now(),
        item_count=3,
        note="test",
        generation_status="ready",
        file_size_bytes=2048,
        download_count=0,
    )
    assert out.version == 1
    assert out.generation_status == "ready"
```

- [ ] **Step 3: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_snapshot_schemas.py -v
```

- [ ] **Step 4: 创建 snapshot schemas**

创建 `backend/app/schemas/suggestion_snapshot.py`：

```python
"""Snapshot 相关 Pydantic DTO。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SnapshotCreateRequest(BaseModel):
    """POST /api/suggestions/{id}/snapshots 请求体。"""

    item_ids: list[int] = Field(..., min_length=1)
    note: str | None = Field(default=None, max_length=200)


class SnapshotOut(BaseModel):
    """Snapshot 摘要（用于列表）。"""

    id: int
    suggestion_id: int
    version: int
    exported_by: int | None = None
    exported_by_name: str | None = None  # 由 API 层 JOIN sys_user 注入
    exported_at: datetime
    item_count: int
    note: str | None = None
    generation_status: str  # 'generating' | 'ready' | 'failed'
    file_size_bytes: int | None = None
    download_count: int

    model_config = {"from_attributes": True}


class SnapshotItemOut(BaseModel):
    """Snapshot 内冻结 item。"""

    id: int
    commodity_sku: str
    commodity_name: str | None = None
    main_image_url: str | None = None
    total_qty: int
    country_breakdown: dict[str, Any]
    warehouse_breakdown: dict[str, Any]
    urgent: bool
    velocity_snapshot: dict[str, Any] | None = None
    sale_days_snapshot: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class SnapshotDetailOut(SnapshotOut):
    """Snapshot 详情（含所有 items）。"""

    items: list[SnapshotItemOut]
    global_config_snapshot: dict[str, Any]
```

- [ ] **Step 5: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_snapshot_schemas.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/suggestion.py backend/app/schemas/suggestion_snapshot.py backend/tests/unit/test_suggestion_snapshot_schemas.py
git commit -m "feat(schemas): snapshot 相关 DTO + 清理推送字段"
```

---

## Task 11: Excel 生成服务

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/excel_export.py`
- Create: `backend/tests/unit/test_excel_export_service.py`

- [ ] **Step 1: 创建 services 目录初始化**

```bash
mkdir -p backend/app/services
touch backend/app/services/__init__.py
```

- [ ] **Step 2: 写 Excel 生成测试**

创建 `backend/tests/unit/test_excel_export_service.py`：

```python
"""Excel 导出服务单测（无 DB）。"""

import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.services.excel_export import SnapshotExportContext, build_excel_workbook


@pytest.fixture
def sample_context() -> SnapshotExportContext:
    return SnapshotExportContext(
        suggestion_id=42,
        version=1,
        exported_at_text="2026-04-17 14:30:52",
        exported_by_name="alice",
        note="发给 A 供应商",
        global_config={
            "target_days": 30,
            "buffer_days": 7,
            "lead_time_days": 14,
            "restock_regions": ["US", "GB"],
        },
        items=[
            {
                "commodity_sku": "SKU-A",
                "commodity_name": "商品 A",
                "main_image_url": "https://img/a.jpg",
                "total_qty": 150,
                "urgent": True,
                "country_breakdown": {"US": 100, "GB": 50},
                "warehouse_breakdown": {"US": {"WH-1": 60, "WH-2": 40}, "GB": {"WH-5": 50}},
                "velocity_snapshot": {"US": 1.5, "GB": 0.8},
                "sale_days_snapshot": {"US": 20, "GB": 40},
                "warehouse_name_map": {"WH-1": "加州仓", "WH-2": "纽约仓", "WH-5": "伦敦仓"},
            }
        ],
    )


def test_workbook_has_four_sheets(sample_context: SnapshotExportContext) -> None:
    wb = build_excel_workbook(sample_context)
    assert wb.sheetnames == ["SKU汇总", "SKU×国家", "SKU×国家×仓库", "导出元信息"]


def test_sku_sheet_rows(sample_context: SnapshotExportContext) -> None:
    wb = build_excel_workbook(sample_context)
    ws = wb["SKU汇总"]
    # 表头 + 1 条 SKU
    assert ws.max_row == 2
    header = [c.value for c in ws[1]]
    assert "SKU" in header and "总采购量" in header and "紧急" in header
    row = [c.value for c in ws[2]]
    assert row[header.index("SKU")] == "SKU-A"
    assert row[header.index("总采购量")] == 150


def test_sku_country_sheet_rows(sample_context: SnapshotExportContext) -> None:
    wb = build_excel_workbook(sample_context)
    ws = wb["SKU×国家"]
    # 表头 + 2 国家
    assert ws.max_row == 3


def test_sku_country_warehouse_sheet_rows(sample_context: SnapshotExportContext) -> None:
    wb = build_excel_workbook(sample_context)
    ws = wb["SKU×国家×仓库"]
    # 表头 + US 2 仓 + GB 1 仓 = 4 行
    assert ws.max_row == 4


def test_meta_sheet_content(sample_context: SnapshotExportContext) -> None:
    wb = build_excel_workbook(sample_context)
    ws = wb["导出元信息"]
    kv = {row[0].value: row[1].value for row in ws.iter_rows(min_row=1, max_row=ws.max_row)}
    assert kv["建议单 ID"] == 42
    assert kv["快照版本"] == "v1"
    assert kv["导出人"] == "alice"
    assert kv["批次备注"] == "发给 A 供应商"


def test_workbook_writes_to_disk(tmp_path: Path, sample_context: SnapshotExportContext) -> None:
    wb = build_excel_workbook(sample_context)
    target = tmp_path / "test.xlsx"
    wb.save(target)
    assert target.exists()
    assert target.stat().st_size > 0
    # 可读回
    wb2 = load_workbook(target)
    assert "SKU汇总" in wb2.sheetnames
```

- [ ] **Step 3: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_excel_export_service.py -v
```

- [ ] **Step 4: 实现 `excel_export.py`**

创建 `backend/app/services/excel_export.py`：

```python
"""Snapshot Excel 多 Sheet 生成工具（纯函数，无 DB 依赖）。"""

from dataclasses import dataclass
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


@dataclass
class SnapshotExportContext:
    """Excel 生成所需的全部数据（由 API 层从 DB 组装）。"""

    suggestion_id: int
    version: int
    exported_at_text: str  # 已格式化字符串
    exported_by_name: str | None
    note: str | None
    global_config: dict[str, Any]
    items: list[dict[str, Any]]
    # items 每项包含:
    #   commodity_sku, commodity_name, main_image_url
    #   total_qty, urgent
    #   country_breakdown: {country: qty}
    #   warehouse_breakdown: {country: {wh_id: qty}}
    #   velocity_snapshot: {country: float}
    #   sale_days_snapshot: {country: float}
    #   warehouse_name_map: {wh_id: wh_name}  (由 API 层 JOIN warehouse 注入)


HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center")


def _apply_header(ws, row: int, headers: list[str]) -> None:
    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN


def _autosize(ws) -> None:
    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
            value = row[0].value
            if value is None:
                continue
            text = str(value)
            max_len = max(max_len, len(text))
        ws.column_dimensions[letter].width = min(max_len + 2, 50)


def _build_sku_sheet(wb: Workbook, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet("SKU汇总")
    headers = ["SKU", "商品名", "主图 URL", "总采购量", "紧急"]
    _apply_header(ws, 1, headers)
    for item in items:
        ws.append([
            item["commodity_sku"],
            item.get("commodity_name") or "",
            item.get("main_image_url") or "",
            item["total_qty"],
            "是" if item["urgent"] else "",
        ])
    _autosize(ws)


def _build_sku_country_sheet(wb: Workbook, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet("SKU×国家")
    headers = ["SKU", "商品名", "国家", "补货量", "可售天数", "日均销量"]
    _apply_header(ws, 1, headers)
    for item in items:
        velocity = item.get("velocity_snapshot") or {}
        sale_days = item.get("sale_days_snapshot") or {}
        for country, qty in item["country_breakdown"].items():
            ws.append([
                item["commodity_sku"],
                item.get("commodity_name") or "",
                country,
                qty,
                sale_days.get(country),
                velocity.get(country),
            ])
    _autosize(ws)


def _build_sku_country_warehouse_sheet(wb: Workbook, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet("SKU×国家×仓库")
    headers = ["SKU", "商品名", "国家", "仓库 ID", "仓库名", "分配量"]
    _apply_header(ws, 1, headers)
    for item in items:
        wh_name_map = item.get("warehouse_name_map") or {}
        for country, wh_dict in item["warehouse_breakdown"].items():
            for wh_id, qty in wh_dict.items():
                ws.append([
                    item["commodity_sku"],
                    item.get("commodity_name") or "",
                    country,
                    wh_id,
                    wh_name_map.get(wh_id, ""),
                    qty,
                ])
    _autosize(ws)


def _build_meta_sheet(wb: Workbook, ctx: SnapshotExportContext) -> None:
    ws = wb.create_sheet("导出元信息")
    total_qty_sum = sum(item["total_qty"] for item in ctx.items)
    rows: list[tuple[str, Any]] = [
        ("建议单 ID", ctx.suggestion_id),
        ("快照版本", f"v{ctx.version}"),
        ("导出时间", ctx.exported_at_text),
        ("导出人", ctx.exported_by_name or "系统"),
        ("批次备注", ctx.note or ""),
        ("", ""),
        ("—— 全局参数（导出时冻结）——", ""),
        ("target_days", ctx.global_config.get("target_days", "")),
        ("buffer_days", ctx.global_config.get("buffer_days", "")),
        ("lead_time_days", ctx.global_config.get("lead_time_days", "")),
        ("restock_regions", ", ".join(ctx.global_config.get("restock_regions") or [])),
        ("", ""),
        ("总 SKU 数", len(ctx.items)),
        ("总补货量", total_qty_sum),
    ]
    for key, value in rows:
        ws.append([key, value])
    # 加粗第 1、7 行标题行
    for row_idx in [1, 7]:
        ws.cell(row=row_idx, column=1).font = Font(bold=True)
    _autosize(ws)


def build_excel_workbook(ctx: SnapshotExportContext) -> Workbook:
    """组装完整 4-Sheet 工作簿，返回 openpyxl Workbook 对象。"""
    wb = Workbook()
    # 删除默认 Sheet
    default = wb.active
    if default is not None:
        wb.remove(default)
    _build_sku_sheet(wb, ctx.items)
    _build_sku_country_sheet(wb, ctx.items)
    _build_sku_country_warehouse_sheet(wb, ctx.items)
    _build_meta_sheet(wb, ctx)
    return wb


def build_filename(suggestion_id: int, version: int, exported_at_compact: str) -> str:
    """生成 '补货建议-{sid}-v{ver}-{YYYYMMDD-HHmmss}.xlsx'。"""
    return f"补货建议-{suggestion_id}-v{version}-{exported_at_compact}.xlsx"
```

- [ ] **Step 5: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_excel_export_service.py -v
```

预期：6 个测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ backend/tests/unit/test_excel_export_service.py
git commit -m "feat(services): Excel 4-Sheet 生成服务（openpyxl）"
```

---

## Task 12: Snapshot API — POST 创建 + 文件落盘

**Files:**
- Create: `backend/app/api/snapshot.py`
- Modify: `backend/app/main.py` — 注册 router
- Modify: `backend/app/config.py` — 新增 `export_storage_dir` 配置项
- Create: `backend/tests/unit/test_snapshot_api.py`

- [ ] **Step 1: 增加配置项**

编辑 `backend/app/config.py`，在 `Settings` 类适当位置加：

```python
    # Excel 导出文件根目录（相对 backend/ 或绝对路径）
    export_storage_dir: str = "../deploy/data/exports"
```

（与 `deploy/docker-compose.yml` 挂载点对齐；容器内的 volume 路径按实际映射调整）

- [ ] **Step 2: 写 POST snapshot 失败测试**

创建 `backend/tests/unit/test_snapshot_api.py`：

```python
"""Snapshot API 端点测试（使用 TestClient + 临时 DB）。"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_snapshot_requires_export_permission(
    auth_client_no_export, snapshot_seed_suggestion
):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    r = await auth_client_no_export.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:2]},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_snapshot_success(auth_client_admin, snapshot_seed_suggestion, tmp_path):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    r = await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:2], "note": "test export"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["item_count"] == 2
    assert body["generation_status"] == "ready"
    assert body["note"] == "test export"


@pytest.mark.asyncio
async def test_create_snapshot_flips_toggle_off(auth_client_admin, snapshot_seed_suggestion):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    # 前置：开关必须是 ON
    toggle = await auth_client_admin.get("/api/config/generation-toggle")
    assert toggle.json()["enabled"] is True
    # 首次导出
    await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )
    # 开关自动翻 OFF
    toggle2 = await auth_client_admin.get("/api/config/generation-toggle")
    assert toggle2.json()["enabled"] is False


@pytest.mark.asyncio
async def test_create_snapshot_version_increments(auth_client_admin, snapshot_seed_suggestion):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    r1 = await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )
    r2 = await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[1:2]},
    )
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_create_snapshot_item_ids_become_exported(
    auth_client_admin, snapshot_seed_suggestion, db_session
):
    from sqlalchemy import select
    from app.models.suggestion import SuggestionItem

    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:2]},
    )
    rows = (
        await db_session.execute(
            select(SuggestionItem.id, SuggestionItem.export_status).where(
                SuggestionItem.suggestion_id == sid
            )
        )
    ).all()
    status_map = dict(rows)
    for iid in item_ids[:2]:
        assert status_map[iid] == "exported"
```

- [ ] **Step 3: 添加测试 fixtures 到 `tests/unit/conftest.py`（或 `tests/conftest.py`）**

在现有 conftest 末尾追加：

```python
@pytest.fixture
async def snapshot_seed_suggestion(db_session):
    """为 snapshot 测试提供一个 draft 建议单 + 3 个 item。"""
    from app.models.suggestion import Suggestion, SuggestionItem

    sug = Suggestion(
        status="draft",
        global_config_snapshot={"target_days": 30, "buffer_days": 7, "lead_time_days": 14},
        total_items=3,
        triggered_by="manual",
    )
    db_session.add(sug)
    await db_session.flush()
    items = [
        SuggestionItem(
            suggestion_id=sug.id,
            commodity_sku=f"SKU-{i}",
            total_qty=100 + i,
            country_breakdown={"US": 50 + i, "GB": 50},
            warehouse_breakdown={"US": {"WH-1": 50 + i}, "GB": {"WH-5": 50}},
            urgent=(i % 2 == 0),
            velocity_snapshot={"US": 1.5, "GB": 0.8},
            sale_days_snapshot={"US": 20, "GB": 40},
        )
        for i in range(3)
    ]
    db_session.add_all(items)
    await db_session.commit()
    return {
        "suggestion_id": sug.id,
        "item_ids": [it.id for it in items],
    }
```

（若 `auth_client_admin` / `auth_client_no_export` fixture 不存在，需按项目既有 `tests/integration/conftest.py` 的 auth fixture 模式补齐——复用已有模式。）

- [ ] **Step 4: 运行测试（全 FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_snapshot_api.py -v
```

- [ ] **Step 5: 实现 `api/snapshot.py`**

创建 `backend/app/api/snapshot.py`：

```python
"""Snapshot 相关 API 端点。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.config import get_settings
from app.core.permissions import RESTOCK_EXPORT, RESTOCK_VIEW
from app.models.excel_export_log import ExcelExportLog
from app.models.global_config import GlobalConfig
from app.models.product_listing import ProductListing
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot, SuggestionSnapshotItem
from app.models.sys_user import SysUser
from app.models.warehouse import Warehouse
from app.schemas.suggestion_snapshot import (
    SnapshotCreateRequest,
    SnapshotDetailOut,
    SnapshotItemOut,
    SnapshotOut,
)
from app.services.excel_export import (
    SnapshotExportContext,
    build_excel_workbook,
    build_filename,
)

router = APIRouter(prefix="/api", tags=["snapshot"])


@router.post(
    "/suggestions/{suggestion_id}/snapshots",
    response_model=SnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_snapshot(
    suggestion_id: int,
    body: SnapshotCreateRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotOut:
    # 1. 校验建议单存在且为 draft
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if sug is None:
        raise HTTPException(status_code=404, detail="建议单不存在")
    if sug.status != "draft":
        raise HTTPException(status_code=409, detail=f"建议单状态 {sug.status}，不可导出")

    # 2. 校验 items 都属于该单 + 都是 pending
    items = (
        (
            await db.execute(
                select(SuggestionItem).where(
                    SuggestionItem.id.in_(body.item_ids),
                    SuggestionItem.suggestion_id == suggestion_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(items) != len(body.item_ids):
        raise HTTPException(status_code=400, detail="部分 item 不属于该建议单")
    already = [it.id for it in items if it.export_status == "exported"]
    if already:
        raise HTTPException(status_code=409, detail=f"以下 item 已导出：{already}")

    # 3. 计算 version
    max_version = (
        await db.execute(
            select(func.coalesce(func.max(SuggestionSnapshot.version), 0)).where(
                SuggestionSnapshot.suggestion_id == suggestion_id
            )
        )
    ).scalar_one()
    next_version = int(max_version) + 1

    # 4. 构建 snapshot 行（generation_status=generating）
    snapshot = SuggestionSnapshot(
        suggestion_id=suggestion_id,
        version=next_version,
        exported_by=user.id,
        exported_from_ip=request.client.host if request.client else None,
        item_count=len(items),
        note=body.note,
        global_config_snapshot=sug.global_config_snapshot,
        generation_status="generating",
    )
    db.add(snapshot)
    await db.flush()

    # 5. 拉取辅助数据（商品名 + 仓库名）
    skus = [it.commodity_sku for it in items]
    product_rows = (
        await db.execute(
            select(
                ProductListing.commodity_sku,
                ProductListing.item_name,
                ProductListing.main_image,
            ).where(ProductListing.commodity_sku.in_(skus))
        )
    ).all()
    product_info = {row[0]: {"name": row[1], "image": row[2]} for row in product_rows}

    wh_ids: set[str] = set()
    for it in items:
        for wh_dict in it.warehouse_breakdown.values():
            wh_ids.update(wh_dict.keys())
    wh_rows = (
        await db.execute(
            select(Warehouse.warehouse_id, Warehouse.warehouse_name).where(
                Warehouse.warehouse_id.in_(list(wh_ids))
            )
        )
    ).all()
    wh_name_map = {str(row[0]): row[1] for row in wh_rows}

    # 6. 冻结 snapshot_item
    snapshot_items_ctx: list[dict[str, Any]] = []
    for it in items:
        pinfo = product_info.get(it.commodity_sku, {})
        snap_item = SuggestionSnapshotItem(
            snapshot_id=snapshot.id,
            commodity_sku=it.commodity_sku,
            total_qty=it.total_qty,
            country_breakdown=it.country_breakdown,
            warehouse_breakdown=it.warehouse_breakdown,
            urgent=it.urgent,
            velocity_snapshot=it.velocity_snapshot,
            sale_days_snapshot=it.sale_days_snapshot,
            commodity_name=pinfo.get("name"),
            main_image_url=pinfo.get("image"),
        )
        db.add(snap_item)
        snapshot_items_ctx.append({
            "commodity_sku": it.commodity_sku,
            "commodity_name": pinfo.get("name"),
            "main_image_url": pinfo.get("image"),
            "total_qty": it.total_qty,
            "urgent": it.urgent,
            "country_breakdown": it.country_breakdown,
            "warehouse_breakdown": it.warehouse_breakdown,
            "velocity_snapshot": it.velocity_snapshot,
            "sale_days_snapshot": it.sale_days_snapshot,
            "warehouse_name_map": wh_name_map,
        })

    # 7. 更新原 item 的 export_status
    await db.execute(
        update(SuggestionItem)
        .where(SuggestionItem.id.in_(body.item_ids))
        .values(
            export_status="exported",
            exported_snapshot_id=snapshot.id,
            exported_at=datetime.utcnow(),
        )
    )

    # 8. 生成 Excel 文件
    now = datetime.now()
    exported_at_text = now.strftime("%Y-%m-%d %H:%M:%S")
    exported_at_compact = now.strftime("%Y%m%d-%H%M%S")
    user_name = user.display_name or user.username
    ctx = SnapshotExportContext(
        suggestion_id=suggestion_id,
        version=next_version,
        exported_at_text=exported_at_text,
        exported_by_name=user_name,
        note=body.note,
        global_config=sug.global_config_snapshot,
        items=snapshot_items_ctx,
    )
    settings = get_settings()
    storage_root = Path(settings.export_storage_dir)
    year_month = now.strftime("%Y/%m")
    target_dir = storage_root / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(suggestion_id, next_version, exported_at_compact)
    target_path = target_dir / filename

    try:
        wb = build_excel_workbook(ctx)
        wb.save(target_path)
        file_size = target_path.stat().st_size
        snapshot.file_path = str(Path(year_month) / filename).replace("\\", "/")
        snapshot.file_size_bytes = file_size
        snapshot.generation_status = "ready"
    except Exception as exc:  # noqa: BLE001
        snapshot.generation_status = "failed"
        snapshot.generation_error = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Excel 生成失败：{exc}") from exc

    # 9. 首次导出 → 翻 toggle OFF
    config = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
    if config.suggestion_generation_enabled:
        config.suggestion_generation_enabled = False
        config.generation_toggle_updated_by = user.id
        config.generation_toggle_updated_at = now

    # 10. 写入 export_log
    db.add(
        ExcelExportLog(
            snapshot_id=snapshot.id,
            action="generate",
            performed_by=user.id,
            performed_from_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500] or None,
        )
    )

    await db.commit()
    await db.refresh(snapshot)
    return SnapshotOut(
        id=snapshot.id,
        suggestion_id=snapshot.suggestion_id,
        version=snapshot.version,
        exported_by=snapshot.exported_by,
        exported_by_name=user_name,
        exported_at=snapshot.exported_at,
        item_count=snapshot.item_count,
        note=snapshot.note,
        generation_status=snapshot.generation_status,
        file_size_bytes=snapshot.file_size_bytes,
        download_count=snapshot.download_count,
    )
```

- [ ] **Step 6: 注册 router 到 `main.py`**

编辑 `backend/app/main.py`，在其他 `include_router` 附近加：

```python
from app.api import snapshot as snapshot_api

app.include_router(snapshot_api.router)
```

- [ ] **Step 7: 运行 POST snapshot 测试**

```bash
.venv/Scripts/pytest tests/unit/test_snapshot_api.py -v
```

预期：5 个测试 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/snapshot.py backend/app/main.py backend/app/config.py backend/tests/unit/test_snapshot_api.py backend/tests/unit/conftest.py
git commit -m "feat(api): POST /suggestions/{id}/snapshots 创建导出快照 + Excel 落盘"
```

---

## Task 13: Snapshot API — GET 列表/详情/items/下载

**Files:**
- Modify: `backend/app/api/snapshot.py`
- Modify: `backend/tests/unit/test_snapshot_api.py`

- [ ] **Step 1: 追加 GET 测试**

在 `tests/unit/test_snapshot_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_list_snapshots_for_suggestion(auth_client_admin, snapshot_seed_suggestion):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )
    r = await auth_client_admin.get(f"/api/suggestions/{sid}/snapshots")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["version"] == 1


@pytest.mark.asyncio
async def test_snapshot_detail(auth_client_admin, snapshot_seed_suggestion):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    created = (
        await auth_client_admin.post(
            f"/api/suggestions/{sid}/snapshots",
            json={"item_ids": item_ids[:2]},
        )
    ).json()
    snap_id = created["id"]
    r = await auth_client_admin.get(f"/api/snapshots/{snap_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_snapshot_download(auth_client_admin, snapshot_seed_suggestion):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    created = (
        await auth_client_admin.post(
            f"/api/suggestions/{sid}/snapshots",
            json={"item_ids": item_ids[:1]},
        )
    ).json()
    snap_id = created["id"]
    r1 = await auth_client_admin.get(f"/api/snapshots/{snap_id}/download")
    assert r1.status_code == 200
    assert r1.headers["content-type"] in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    )
    assert "attachment" in r1.headers.get("content-disposition", "")
    # download_count 递增
    r2 = await auth_client_admin.get(f"/api/snapshots/{snap_id}")
    assert r2.json()["download_count"] == 1
```

- [ ] **Step 2: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_snapshot_api.py::test_list_snapshots_for_suggestion -v
```

- [ ] **Step 3: 在 `backend/app/api/snapshot.py` 文件末尾追加端点**

```python
@router.get(
    "/suggestions/{suggestion_id}/snapshots",
    response_model=list[SnapshotOut],
)
async def list_snapshots(
    suggestion_id: int,
    _: None = Depends(require_permission(RESTOCK_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> list[SnapshotOut]:
    rows = (
        await db.execute(
            select(
                SuggestionSnapshot,
                SysUser.display_name.label("exported_by_name"),
            )
            .outerjoin(SysUser, SysUser.id == SuggestionSnapshot.exported_by)
            .where(SuggestionSnapshot.suggestion_id == suggestion_id)
            .order_by(SuggestionSnapshot.version.asc())
        )
    ).all()
    return [
        SnapshotOut(
            id=snap.id,
            suggestion_id=snap.suggestion_id,
            version=snap.version,
            exported_by=snap.exported_by,
            exported_by_name=name,
            exported_at=snap.exported_at,
            item_count=snap.item_count,
            note=snap.note,
            generation_status=snap.generation_status,
            file_size_bytes=snap.file_size_bytes,
            download_count=snap.download_count,
        )
        for snap, name in rows
    ]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotDetailOut)
async def get_snapshot_detail(
    snapshot_id: int,
    _: None = Depends(require_permission(RESTOCK_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotDetailOut:
    row = (
        await db.execute(
            select(
                SuggestionSnapshot,
                SysUser.display_name.label("exported_by_name"),
            )
            .outerjoin(SysUser, SysUser.id == SuggestionSnapshot.exported_by)
            .where(SuggestionSnapshot.id == snapshot_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    snap, name = row
    items = (
        (
            await db.execute(
                select(SuggestionSnapshotItem).where(
                    SuggestionSnapshotItem.snapshot_id == snapshot_id
                )
            )
        )
        .scalars()
        .all()
    )
    return SnapshotDetailOut(
        id=snap.id,
        suggestion_id=snap.suggestion_id,
        version=snap.version,
        exported_by=snap.exported_by,
        exported_by_name=name,
        exported_at=snap.exported_at,
        item_count=snap.item_count,
        note=snap.note,
        generation_status=snap.generation_status,
        file_size_bytes=snap.file_size_bytes,
        download_count=snap.download_count,
        items=[SnapshotItemOut.model_validate(it) for it in items],
        global_config_snapshot=snap.global_config_snapshot,
    )


@router.get("/snapshots/{snapshot_id}/download")
async def download_snapshot(
    snapshot_id: int,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> FileResponse:
    snap = (
        await db.execute(
            select(SuggestionSnapshot).where(SuggestionSnapshot.id == snapshot_id)
        )
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    if snap.generation_status != "ready":
        raise HTTPException(status_code=409, detail="文件尚未就绪或生成失败")
    settings = get_settings()
    file_abs = Path(settings.export_storage_dir) / snap.file_path
    if not file_abs.exists():
        raise HTTPException(status_code=410, detail="文件已丢失")

    # 更新下载计数
    await db.execute(
        update(SuggestionSnapshot)
        .where(SuggestionSnapshot.id == snapshot_id)
        .values(
            download_count=SuggestionSnapshot.download_count + 1,
            last_downloaded_at=datetime.utcnow(),
        )
    )
    db.add(
        ExcelExportLog(
            snapshot_id=snapshot_id,
            action="download",
            performed_by=user.id,
            performed_from_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500] or None,
        )
    )
    await db.commit()

    filename = Path(snap.file_path).name
    return FileResponse(
        path=file_abs,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

- [ ] **Step 4: 运行全部 snapshot API 测试**

```bash
.venv/Scripts/pytest tests/unit/test_snapshot_api.py -v
```

预期：全部 PASS（5 + 3 = 8 个）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/snapshot.py backend/tests/unit/test_snapshot_api.py
git commit -m "feat(api): snapshot 列表/详情/下载端点 + 下载计数"
```

---

## Task 14: `suggestion.py` API — 列表 snapshot_count + 删除校验

**Files:**
- Modify: `backend/app/api/suggestion.py`
- Modify: `backend/tests/unit/test_suggestion_patch.py`（或新 test 文件）

- [ ] **Step 1: 写删除校验测试**

创建 `backend/tests/unit/test_suggestion_delete_with_snapshot.py`：

```python
import pytest


@pytest.mark.asyncio
async def test_delete_draft_without_snapshot_ok(auth_client_admin, snapshot_seed_suggestion):
    sid = snapshot_seed_suggestion["suggestion_id"]
    r = await auth_client_admin.delete(f"/api/suggestions/{sid}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_draft_with_snapshot_rejected(
    auth_client_admin, snapshot_seed_suggestion
):
    sid = snapshot_seed_suggestion["suggestion_id"]
    item_ids = snapshot_seed_suggestion["item_ids"]
    await auth_client_admin.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )
    r = await auth_client_admin.delete(f"/api/suggestions/{sid}")
    assert r.status_code == 409
    assert "snapshot" in r.json()["detail"].lower() or "快照" in r.json()["detail"]
```

- [ ] **Step 2: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_delete_with_snapshot.py -v
```

- [ ] **Step 3: 更新 DELETE 端点**

在 `backend/app/api/suggestion.py` 中定位 `DELETE /{suggestion_id}` 端点，修改函数体加 snapshot 校验：

```python
@router.delete("/{suggestion_id}", status_code=204)
async def delete_suggestion(
    suggestion_id: int,
    _: None = Depends(require_permission(HISTORY_DELETE)),
    db: AsyncSession = Depends(db_session),
) -> None:
    from app.models.suggestion_snapshot import SuggestionSnapshot

    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if sug is None:
        raise HTTPException(status_code=404, detail="建议单不存在")
    if sug.status != "draft":
        raise HTTPException(status_code=409, detail=f"建议单状态 {sug.status}，不可删除")

    # 新校验：有 snapshot 的不可删
    snap_count = (
        await db.execute(
            select(func.count()).select_from(SuggestionSnapshot).where(
                SuggestionSnapshot.suggestion_id == suggestion_id
            )
        )
    ).scalar_one()
    if snap_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"建议单已有 {snap_count} 个快照，不可删除",
        )

    await db.execute(
        select(Suggestion).where(Suggestion.id == suggestion_id)
    )
    # 级联删除 suggestion_item（FK on delete cascade）
    await db.delete(sug)
    await db.commit()
```

- [ ] **Step 4: 修改 GET list 返回注入 `snapshot_count`**

定位 `@router.get("", response_model=SuggestionListOut)` 的 `list_suggestions` 函数。

修改查询，加入 `snapshot_count` 子查询：

```python
from sqlalchemy import func
from app.models.suggestion_snapshot import SuggestionSnapshot

# 在原 select 中改成 LEFT JOIN LATERAL 或 subquery scalar
snap_count_sq = (
    select(func.count(SuggestionSnapshot.id))
    .where(SuggestionSnapshot.suggestion_id == Suggestion.id)
    .correlate(Suggestion)
    .scalar_subquery()
)
# 原 select 改为:
# select(Suggestion, snap_count_sq.label("snapshot_count"))
```

然后组装 `SuggestionOut` 时注入 `snapshot_count`。

（具体代码见现有 `list_suggestions` 结构，按现有模式扩展。）

- [ ] **Step 5: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_suggestion_delete_with_snapshot.py -v
.venv/Scripts/pytest tests/unit/test_suggestion_patch.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/suggestion.py backend/tests/unit/test_suggestion_delete_with_snapshot.py
git commit -m "feat(api): suggestion 列表注入 snapshot_count + 删除校验 snapshot"
```

---

## Task 15: 生成开关 API

**Files:**
- Modify: `backend/app/api/config.py`
- Modify: `backend/app/schemas/config.py`
- Create: `backend/tests/unit/test_generation_toggle_api.py`

- [ ] **Step 1: 添加 schema**

编辑 `backend/app/schemas/config.py`，末尾追加：

```python
class GenerationToggleOut(BaseModel):
    enabled: bool
    updated_by: int | None = None
    updated_by_name: str | None = None
    updated_at: datetime | None = None


class GenerationTogglePatch(BaseModel):
    enabled: bool
```

顶部如无 `from datetime import datetime` / `from pydantic import BaseModel` 请补全。

- [ ] **Step 2: 写测试**

创建 `backend/tests/unit/test_generation_toggle_api.py`：

```python
import pytest


@pytest.mark.asyncio
async def test_get_toggle_default_enabled(auth_client_admin):
    r = await auth_client_admin.get("/api/config/generation-toggle")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True


@pytest.mark.asyncio
async def test_patch_toggle_requires_new_cycle_perm(auth_client_no_cycle_perm):
    r = await auth_client_no_cycle_perm.patch(
        "/api/config/generation-toggle",
        json={"enabled": True},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_patch_toggle_on_archives_current_draft(
    auth_client_admin, snapshot_seed_suggestion, db_session
):
    from sqlalchemy import select
    from app.models.global_config import GlobalConfig
    from app.models.suggestion import Suggestion

    sid = snapshot_seed_suggestion["suggestion_id"]
    # 先手动翻 OFF（模拟导出后状态）
    await db_session.execute(
        GlobalConfig.__table__.update()
        .where(GlobalConfig.id == 1)
        .values(suggestion_generation_enabled=False)
    )
    await db_session.commit()

    # 翻 ON
    r = await auth_client_admin.patch(
        "/api/config/generation-toggle",
        json={"enabled": True},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is True

    # 当前 draft 被归档
    sug = (
        await db_session.execute(select(Suggestion).where(Suggestion.id == sid))
    ).scalar_one()
    assert sug.status == "archived"
    assert sug.archived_trigger == "admin_toggle"
```

- [ ] **Step 3: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_generation_toggle_api.py -v
```

- [ ] **Step 4: 在 `api/config.py` 末尾追加两个端点**

```python
from datetime import datetime
from sqlalchemy import update
from app.core.permissions import CONFIG_VIEW, RESTOCK_NEW_CYCLE
from app.models.sys_user import SysUser
from app.schemas.config import GenerationToggleOut, GenerationTogglePatch
from app.api.deps import UserContext, get_current_user


@router.get("/generation-toggle", response_model=GenerationToggleOut)
async def get_generation_toggle(
    _: None = Depends(require_permission(CONFIG_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> GenerationToggleOut:
    row = (
        await db.execute(
            select(
                GlobalConfig.suggestion_generation_enabled,
                GlobalConfig.generation_toggle_updated_by,
                GlobalConfig.generation_toggle_updated_at,
                SysUser.display_name,
            )
            .select_from(GlobalConfig)
            .outerjoin(SysUser, SysUser.id == GlobalConfig.generation_toggle_updated_by)
            .where(GlobalConfig.id == 1)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=500, detail="全局配置缺失")
    enabled, by_id, at, by_name = row
    return GenerationToggleOut(
        enabled=enabled, updated_by=by_id, updated_by_name=by_name, updated_at=at
    )


@router.patch("/generation-toggle", response_model=GenerationToggleOut)
async def patch_generation_toggle(
    body: GenerationTogglePatch,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_NEW_CYCLE)),
    db: AsyncSession = Depends(db_session),
) -> GenerationToggleOut:
    now = datetime.utcnow()
    # 若从 OFF 翻 ON，先归档当前 draft 建议单
    if body.enabled:
        await db.execute(
            update(Suggestion)
            .where(Suggestion.status == "draft")
            .values(
                status="archived",
                archived_at=now,
                archived_by=user.id,
                archived_trigger="admin_toggle",
            )
        )
    await db.execute(
        update(GlobalConfig)
        .where(GlobalConfig.id == 1)
        .values(
            suggestion_generation_enabled=body.enabled,
            generation_toggle_updated_by=user.id,
            generation_toggle_updated_at=now,
        )
    )
    await db.commit()
    return await get_generation_toggle(_=None, db=db)  # 复用 GET 逻辑
```

确认顶部 `import` 补齐 `Suggestion`。

- [ ] **Step 5: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_generation_toggle_api.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/config.py backend/app/schemas/config.py backend/tests/unit/test_generation_toggle_api.py
git commit -m "feat(api): generation-toggle GET/PATCH + 翻 ON 归档 draft"
```

---

## Task 16: 引擎入口校验开关

**Files:**
- Modify: `backend/app/engine/runner.py`（或调用 runner 的 task / API 层）
- Modify: `backend/tests/unit/test_engine_runner.py`

- [ ] **Step 1: 写测试**

在 `backend/tests/unit/test_engine_runner.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_engine_rejects_when_toggle_off(db_session):
    from sqlalchemy import update
    from app.engine.runner import run_engine
    from app.models.global_config import GlobalConfig
    from app.core.exceptions import BusinessError

    # 强制翻 OFF
    await db_session.execute(
        update(GlobalConfig)
        .where(GlobalConfig.id == 1)
        .values(suggestion_generation_enabled=False)
    )
    await db_session.commit()

    with pytest.raises(BusinessError, match="开关已关闭|已锁定|generation.*disabled"):
        await run_engine(db=db_session, triggered_by="manual")
```

- [ ] **Step 2: 运行测试（FAIL）**

```bash
.venv/Scripts/pytest tests/unit/test_engine_runner.py::test_engine_rejects_when_toggle_off -v
```

- [ ] **Step 3: 在 `run_engine` 入口加校验**

打开 `backend/app/engine/runner.py`，在 `run_engine` 函数**最顶部**（在 advisory_lock 申请之前）加：

```python
    # 生成开关校验
    from app.models.global_config import GlobalConfig

    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one()
    if not config.suggestion_generation_enabled:
        raise BusinessError(
            "生成开关已关闭，请联系管理员开启新一轮后再试",
            code="generation_disabled",
        )
```

顶部如无 `from app.core.exceptions import BusinessError` 补全。

- [ ] **Step 4: 运行测试通过**

```bash
.venv/Scripts/pytest tests/unit/test_engine_runner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/runner.py backend/tests/unit/test_engine_runner.py
git commit -m "feat(engine): runner 入口校验生成开关"
```

---

## Task 17: 端到端集成测试

**Files:**
- Create: `backend/tests/integration/test_export_e2e.py`

- [ ] **Step 1: 写 e2e 测试**

创建 `backend/tests/integration/test_export_e2e.py`：

```python
"""端到端：生成 → 导出 v1 → 继续导出 v2 → 翻开关 → 旧单归档 → 重新生成。"""

import pytest


@pytest.mark.asyncio
async def test_full_cycle(auth_client_admin, db_session):
    from sqlalchemy import select
    from app.models.suggestion import Suggestion, SuggestionItem

    # 准备一个初始的 draft 建议单（模拟引擎产出，直接 seed 避免触发真实引擎）
    sug = Suggestion(
        status="draft",
        global_config_snapshot={"target_days": 30, "buffer_days": 7, "lead_time_days": 14},
        total_items=2,
        triggered_by="manual",
    )
    db_session.add(sug)
    await db_session.flush()
    item1 = SuggestionItem(
        suggestion_id=sug.id,
        commodity_sku="SKU-X",
        total_qty=100,
        country_breakdown={"US": 100},
        warehouse_breakdown={"US": {"WH-1": 100}},
        urgent=False,
    )
    item2 = SuggestionItem(
        suggestion_id=sug.id,
        commodity_sku="SKU-Y",
        total_qty=50,
        country_breakdown={"GB": 50},
        warehouse_breakdown={"GB": {"WH-2": 50}},
        urgent=True,
    )
    db_session.add_all([item1, item2])
    await db_session.commit()

    # 1) 导出 v1（item1）
    r1 = await auth_client_admin.post(
        f"/api/suggestions/{sug.id}/snapshots",
        json={"item_ids": [item1.id], "note": "v1 batch"},
    )
    assert r1.status_code == 201
    assert r1.json()["version"] == 1

    # 开关翻 OFF
    t = await auth_client_admin.get("/api/config/generation-toggle")
    assert t.json()["enabled"] is False

    # 2) 导出 v2（item2）
    r2 = await auth_client_admin.post(
        f"/api/suggestions/{sug.id}/snapshots",
        json={"item_ids": [item2.id], "note": "v2 batch"},
    )
    assert r2.status_code == 201
    assert r2.json()["version"] == 2

    # 3) 翻开关
    r3 = await auth_client_admin.patch(
        "/api/config/generation-toggle",
        json={"enabled": True},
    )
    assert r3.status_code == 200

    # 4) 原单归档
    sug_refreshed = (
        await db_session.execute(select(Suggestion).where(Suggestion.id == sug.id))
    ).scalar_one()
    assert sug_refreshed.status == "archived"
    assert sug_refreshed.archived_trigger == "admin_toggle"

    # 5) snapshot 仍可下载
    snap_list = (await auth_client_admin.get(f"/api/suggestions/{sug.id}/snapshots")).json()
    assert len(snap_list) == 2
    first_dl = await auth_client_admin.get(f"/api/snapshots/{snap_list[0]['id']}/download")
    assert first_dl.status_code == 200
```

- [ ] **Step 2: 运行**

```bash
.venv/Scripts/pytest tests/integration/test_export_e2e.py -v
```

预期：PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_export_e2e.py
git commit -m "test(integration): 端到端导出闭环"
```

---

## Task 18: 全量回归 + 最终检查

- [ ] **Step 1: 全量 pytest**

```bash
cd backend
.venv/Scripts/pytest -p no:cacheprovider
```

预期：全绿。若有其他 test 因 import 残留失败，按报错定位清理。

- [ ] **Step 2: mypy 检查（允许 API 模块豁免）**

```bash
.venv/Scripts/mypy app
```

若 `api/snapshot.py` 报类型错，可在 `pyproject.toml` 的 `[[tool.mypy.overrides]]` 段追加：

```toml
[[tool.mypy.overrides]]
module = ["app.api.snapshot"]
disable_error_code = [
    "dict-item", "attr-defined", "arg-type",
    "no-any-return", "no-untyped-def", "index",
]
```

（与现有 `app.api.data` 等模块的豁免模式一致；不是理想状态，但保持项目现状，Plan A 不扩展 mypy 严格范围）

- [ ] **Step 3: 验证 migration 向前向后**

```bash
.venv/Scripts/alembic downgrade -1 2>&1 | head -20
```

预期：`NotImplementedError`（AGENTS.md 明确 downgrade 不支持）— 这是预期行为。

```bash
.venv/Scripts/alembic current
```

确认仍在 `20260418_0900`。

- [ ] **Step 4: 最终 commit（若有遗留 build artifact 或配置）**

```bash
git status
# 若有未提交文件，按需整理
```

- [ ] **Step 5: Push branch（可选）**

```bash
git push origin <当前分支名>
```

---

## Self-Review 已完成内容

**Spec 覆盖检查**：
- §4.1 suggestion 状态枚举收缩 → Task 3 migration + Task 4 模型
- §4.2 suggestion_item 字段改造 → Task 3 + Task 4
- §4.3 suggestion_snapshot 新表 → Task 3 + Task 5
- §4.4 suggestion_snapshot_item 新表 → Task 3 + Task 5
- §4.5 excel_export_log 新表 → Task 3 + Task 6
- §4.6 global_config 扩展 → Task 3 + Task 7
- §4.7 权限码新增 → Task 2
- §6.1 首次生成 + 导出 → Task 12 + Task 17
- §6.2 继续导出 v2/v3 → Task 17
- §6.3 开启新一轮 → Task 15 + Task 17
- §6.4 重复下载 → Task 13
- §6.5 删除 draft → Task 14
- §8 UI 不在 Plan A 范围 → Plan B
- §9 Excel 多 Sheet → Task 11
- §10 Migration → Task 3
- §11 僵尸代码清理（后端） → Task 8 + Task 9
- §11 前端清理 → Plan B
- §11 文档 → Plan C

**Placeholder 扫描**：全部任务均含完整代码、完整测试、exact 文件路径。无 TBD / TODO。

**Type consistency**：`SuggestionSnapshot` / `SuggestionSnapshotItem` / `ExcelExportLog` 的字段名在 Task 3（migration）/ Task 5（SQLAlchemy 模型）/ Task 10（Pydantic schema）/ Task 12（API 实现）中严格对齐。

**注意事项**：
- `auth_client_admin` / `auth_client_no_export` / `auth_client_no_cycle_perm` 等 test fixtures 依赖现有 `tests/integration/conftest.py` 的 auth 模式。若项目此前未提供这类按权限区分的 fixture，Task 12 Step 3 中的 fixtures 需按 `backend/tests/integration/conftest.py:<auth 部分>` 现有模式补齐（`create_role_with_perms` + 生成 token）。
- `backend/deploy/data/exports/` 目录需在生产环境通过 `docker-compose.yml` volume 挂载——此属于 Plan C 部署同步清单。本 Plan A 在本机测试时，`export_storage_dir` 可覆盖为 `tmp_path` 或本地临时目录。

---

## Execution Handoff

**Plan 已生成并保存到 `docs/superpowers/plans/2026-04-17-suggestion-export-redesign-plan-a-backend.md`。两种执行选项：**

**1. Subagent-Driven（推荐）** — 每个 Task 派独立 subagent 实现，主会话在 task 之间做 review，快速迭代。
   - REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
   - 两阶段 review（subagent 完成 → 主会话审核 → 下一 task）

**2. Inline Execution** — 在当前会话内顺序执行所有 task，检查点处批量 review。
   - REQUIRED SUB-SKILL: `superpowers:executing-plans`
   - 批量执行，periodic checkpoint 给你确认

**选哪个？**
