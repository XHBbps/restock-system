"""End-to-end export loop integration test."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.global_config import GlobalConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot
from tests.integration import factories


class _Ctx:
    def __init__(self) -> None:
        self.payload: dict = {"triggered_by": "test"}

    async def progress(self, **_: object) -> None:
        return None


def _set_export_dir(monkeypatch) -> None:
    from app import config as cfg_mod

    export_dir = Path("backend/.test_exports").resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(export_dir), raising=False)


@pytest.mark.asyncio
async def test_export_closed_loop(
    client, engine_session_factory, db_session, monkeypatch
) -> None:
    _set_export_dir(monkeypatch)

    today = date.today()
    async with engine_session_factory() as db:
        await factories.seed_minimum_dataset(db, today)
        gc = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
        gc.suggestion_generation_enabled = True
        await db.commit()

    from app.engine import calc_engine_job as job_module
    from app.engine.runner import run_engine

    monkeypatch.setattr(job_module, "async_session_factory", engine_session_factory)
    await job_module.calc_engine_job(_Ctx())  # type: ignore[arg-type]

    async with engine_session_factory() as db:
        gc = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
        suggestion = (
            await db.execute(
                select(Suggestion).where(Suggestion.status == "draft").order_by(Suggestion.id.desc())
            )
        ).scalar_one()
        suggestion_id = suggestion.id
    assert gc.suggestion_generation_enabled is False

    second_sid = await run_engine(_Ctx(), triggered_by="test")  # type: ignore[arg-type]
    assert second_sid is None

    async with engine_session_factory() as db:
        items = (
            await db.execute(
                select(SuggestionItem.id).where(SuggestionItem.suggestion_id == suggestion_id)
            )
        ).scalars().all()
    assert items, "run_engine did not produce any item"

    procurement_resp = await client.post(
        f"/api/suggestions/{suggestion_id}/snapshots/procurement",
        json={"item_ids": items[:1], "note": "e2e"},
    )
    assert procurement_resp.status_code == 201, procurement_resp.text
    procurement_snap = procurement_resp.json()
    snap_id = procurement_snap["id"]
    assert procurement_snap["snapshot_type"] == "procurement"
    assert procurement_snap["version"] == 1
    assert procurement_snap["generation_status"] == "ready"

    restock_resp = await client.post(
        f"/api/suggestions/{suggestion_id}/snapshots/restock",
        json={"item_ids": items[:1], "note": "e2e"},
    )
    assert restock_resp.status_code == 201, restock_resp.text
    assert restock_resp.json()["snapshot_type"] == "restock"

    dl = await client.get(f"/api/snapshots/{snap_id}/download")
    assert dl.status_code == 200
    assert "attachment" in dl.headers.get("content-disposition", "")
    assert len(dl.content) > 0

    patch_resp = await client.patch("/api/config/generation-toggle", json={"enabled": True})
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

    assert sug.status == "archived"
    assert sug.archived_trigger == "admin_toggle"
    assert snap_row.suggestion_id == suggestion_id
