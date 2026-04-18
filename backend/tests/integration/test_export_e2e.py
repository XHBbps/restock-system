"""端到端导出闭环集成测试。

覆盖核心链路：
    run_engine → POST snapshot (Excel 落盘 + 首次关开关)
    → GET 下载 → PATCH 翻 ON (归档 draft + 允许再跑)
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.engine.runner import run_engine
from app.models.global_config import GlobalConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot
from tests.integration import factories


class _Ctx:
    def __init__(self) -> None:
        self.payload: dict = {"triggered_by": "test"}

    async def progress(self, **_: object) -> None:
        return None


@pytest.mark.asyncio
async def test_export_closed_loop(
    client, engine_session_factory, db_session, tmp_path, monkeypatch
) -> None:
    """单次 run_engine → 导出 snapshot → 自动翻 OFF → toggle PATCH ON 归档 draft。"""
    from app import config as cfg_mod

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    # --- 1. 最小数据集 + 开关 ON ---
    today = date.today()
    async with engine_session_factory() as db:
        await factories.seed_minimum_dataset(db, today)
        # seed_minimum_dataset 已经建了 GlobalConfig，确保开关 ON
        gc = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
        gc.suggestion_generation_enabled = True
        await db.commit()

    # --- 2. run_engine → 得到 draft suggestion ---
    suggestion_id = await run_engine(_Ctx(), triggered_by="test")  # type: ignore[arg-type]
    assert suggestion_id is not None

    # 从 draft suggestion 拿到第一个 item
    async with engine_session_factory() as db:
        items = (
            await db.execute(
                select(SuggestionItem.id).where(SuggestionItem.suggestion_id == suggestion_id)
            )
        ).scalars().all()
    assert items, "run_engine 没有产出任何 item"

    # --- 3. POST /suggestions/{id}/snapshots → Excel 落盘 + 首次翻 OFF ---
    resp = await client.post(
        f"/api/suggestions/{suggestion_id}/snapshots",
        json={"item_ids": items[:1], "note": "e2e"},
    )
    assert resp.status_code == 201, resp.text
    snap = resp.json()
    snap_id = snap["id"]
    assert snap["version"] == 1
    assert snap["generation_status"] == "ready"

    # --- 4. 下载 Excel ---
    dl = await client.get(f"/api/snapshots/{snap_id}/download")
    assert dl.status_code == 200
    assert "attachment" in dl.headers.get("content-disposition", "")
    assert len(dl.content) > 0

    # --- 5. 首次导出后开关应当 OFF ---
    async with engine_session_factory() as db:
        gc = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
    assert gc.suggestion_generation_enabled is False

    # --- 6. run_engine 在 OFF 状态下直接返回 None ---
    second_sid = await run_engine(_Ctx(), triggered_by="test")  # type: ignore[arg-type]
    assert second_sid is None

    # --- 7. PATCH /api/config/generation-toggle → ON 会归档 draft ---
    patch_resp = await client.patch(
        "/api/config/generation-toggle", json={"enabled": True}
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["enabled"] is True
    assert body["updated_by"] == 1

    async with engine_session_factory() as db:
        sug = (
            await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
        ).scalar_one()
        snap_row = (
            await db.execute(
                select(SuggestionSnapshot).where(SuggestionSnapshot.id == snap_id)
            )
        ).scalar_one()

    # 原 draft 已被 admin_toggle 归档，snapshot 不受影响
    assert sug.status == "archived"
    assert sug.archived_trigger == "admin_toggle"
    assert snap_row.suggestion_id == suggestion_id
