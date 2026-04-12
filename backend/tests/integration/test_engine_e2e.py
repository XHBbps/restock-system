"""端到端引擎集成测试。"""
from datetime import date

import pytest
from sqlalchemy import select

from app.engine.runner import run_engine
from app.models.suggestion import Suggestion, SuggestionItem
from tests.integration import factories


class _TestContext:
    """Minimal JobContext for testing."""
    def __init__(self):
        self.steps = []
        self.payload = {"triggered_by": "test"}

    async def progress(self, **kwargs):
        self.steps.append(kwargs.get("current_step", ""))


@pytest.mark.asyncio(loop_scope="session")
class TestEngineE2E:

    async def test_engine_happy_path_generates_suggestion(
        self, engine_session_factory, db_engine
    ):
        """最小数据集 → run_engine → 建议单生成的完整链路验证。"""
        today = date.today()

        async with engine_session_factory() as db:
            await factories.seed_minimum_dataset(db, today)

        ctx = _TestContext()
        suggestion_id = await run_engine(ctx, triggered_by="test")

        # 返回非 None 的 suggestion_id
        assert suggestion_id is not None, "run_engine 应返回 suggestion_id，但返回了 None"

        sug_status = None
        items_count = 0
        item_sku = None
        item_total_qty = None
        item_country_breakdown = None
        item_velocity_snapshot = None
        item_sale_days_snapshot = None

        async with engine_session_factory() as db:
            sug = (
                await db.execute(
                    select(Suggestion).where(Suggestion.id == suggestion_id)
                )
            ).scalar_one_or_none()
            assert sug is not None, f"suggestion id={suggestion_id} 未找到"
            sug_status = sug.status

            items = (
                await db.execute(
                    select(SuggestionItem).where(
                        SuggestionItem.suggestion_id == suggestion_id
                    )
                )
            ).scalars().all()
            items_count = len(items)
            if items:
                item = items[0]
                item_sku = item.commodity_sku
                item_total_qty = item.total_qty
                item_country_breakdown = item.country_breakdown
                item_velocity_snapshot = item.velocity_snapshot
                item_sale_days_snapshot = item.sale_days_snapshot

        # 归还所有 pool 连接，避免后续 _setup_db drop_all 时连接冲突
        await db_engine.dispose()

        # 断言 suggestion 表有 status='draft' 的记录
        assert sug_status == "draft", f"期望 status='draft'，实际为 '{sug_status}'"

        # 断言 suggestion_item 表有该 suggestion_id 的条目
        assert items_count > 0, "suggestion_item 表应有至少一条记录"

        # 条目的 commodity_sku 匹配 fixture 数据
        assert item_sku == factories._DEFAULT_SKU, (
            f"期望 commodity_sku='{factories._DEFAULT_SKU}'，实际 '{item_sku}'"
        )

        # total_qty > 0
        assert item_total_qty is not None and item_total_qty > 0, (
            f"total_qty 应 > 0，实际为 {item_total_qty}"
        )

        # country_breakdown 包含 "US"
        assert item_country_breakdown and "US" in item_country_breakdown, (
            f"country_breakdown 应包含 'US'，实际为 {item_country_breakdown}"
        )

        # velocity_snapshot 和 sale_days_snapshot 非 None
        assert item_velocity_snapshot is not None, "velocity_snapshot 不应为 None"
        assert item_sale_days_snapshot is not None, "sale_days_snapshot 不应为 None"

        # ctx.steps 有至少 6 个进度回调（Step 1-6 + 完成）
        assert len(ctx.steps) >= 6, (
            f"期望至少 6 个进度回调，实际 {len(ctx.steps)} 个：{ctx.steps}"
        )

    async def test_engine_no_enabled_sku_returns_none(
        self, engine_session_factory, db_engine
    ):
        """无启用 SKU 时 run_engine 应返回 None，并记录完成步骤。"""
        async with engine_session_factory() as db:
            await factories.seed_global_config(db)
            await db.commit()

        ctx = _TestContext()
        result = await run_engine(ctx, triggered_by="test")

        await db_engine.dispose()

        assert result is None, f"无 SKU 时 run_engine 应返回 None，实际返回 {result}"
        assert any("完成" in (s or "") for s in ctx.steps), (
            f"ctx.steps 应包含 '完成'，实际为 {ctx.steps}"
        )

    async def test_engine_archives_previous_draft(
        self, engine_session_factory, db_engine
    ):
        """连续两次 run_engine：第一次产生 draft，第二次将其归档并产生新 draft。"""
        today = date.today()

        async with engine_session_factory() as db:
            await factories.seed_minimum_dataset(db, today)

        ctx1 = _TestContext()
        first_id = await run_engine(ctx1, triggered_by="test-first")

        assert first_id is not None, "第一次 run_engine 应返回 suggestion_id"

        ctx2 = _TestContext()
        second_id = await run_engine(ctx2, triggered_by="test-second")

        assert second_id is not None, "第二次 run_engine 应返回 suggestion_id"
        assert second_id != first_id, "第二次应产生新建议单（不同 id）"

        first_status = None
        second_status = None

        async with engine_session_factory() as db:
            sug1 = (
                await db.execute(
                    select(Suggestion).where(Suggestion.id == first_id)
                )
            ).scalar_one()
            first_status = sug1.status

            sug2 = (
                await db.execute(
                    select(Suggestion).where(Suggestion.id == second_id)
                )
            ).scalar_one()
            second_status = sug2.status

        await db_engine.dispose()

        # 旧 draft 应已被归档
        assert first_status == "archived", (
            f"第一次建议单在第二次运行后应为 archived，实际 '{first_status}'"
        )

        # 新建议单应为 draft
        assert second_status == "draft", (
            f"第二次建议单应为 draft，实际 '{second_status}'"
        )
