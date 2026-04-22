"""DELETE /api/suggestions/{id} rejects suggestions that already have snapshots."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.global_config import GlobalConfig


def _set_export_dir(monkeypatch) -> None:
    from app import config as cfg_mod

    export_dir = Path("backend/.test_exports").resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(export_dir), raising=False)


@pytest.fixture
async def draft_sug(db_session):
    from app.models.suggestion import Suggestion, SuggestionItem

    sug = Suggestion(
        status="draft",
        global_config_snapshot={"target_days": 30, "buffer_days": 7, "lead_time_days": 14},
        total_items=1,
        restock_item_count=1,
        triggered_by="manual",
    )
    db_session.add(sug)
    await db_session.flush()
    item = SuggestionItem(
        suggestion_id=sug.id,
        commodity_sku="SKU-DEL-1",
        total_qty=10,
        country_breakdown={"US": 10},
        warehouse_breakdown={"US": {"WH-1": 10}},
        urgent=False,
    )
    db_session.add(item)
    await db_session.commit()
    return {"id": sug.id, "item_ids": [item.id]}


@pytest.fixture
async def ensure_gc(db_session):
    gc = (
        await db_session.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    if gc is None:
        import bcrypt

        db_session.add(
            GlobalConfig(
                id=1,
                login_password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()).decode(),
                suggestion_generation_enabled=True,
            )
        )
    else:
        gc.suggestion_generation_enabled = True
    await db_session.commit()


@pytest.mark.asyncio
async def test_delete_draft_without_snapshot_ok(client, draft_sug, ensure_gc):
    resp = await client.delete(f"/api/suggestions/{draft_sug['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_draft_with_snapshot_rejected(client, draft_sug, ensure_gc, monkeypatch):
    _set_export_dir(monkeypatch)
    await client.post(
        f"/api/suggestions/{draft_sug['id']}/snapshots/restock",
        json={"item_ids": draft_sug["item_ids"]},
    )

    resp = await client.delete(f"/api/suggestions/{draft_sug['id']}")

    assert resp.status_code == 409
    body = resp.json()
    combined = str(body).lower()
    assert "snapshot" in combined or "快照" in combined


@pytest.mark.asyncio
async def test_list_includes_split_snapshot_counts(client, draft_sug, ensure_gc):
    resp = await client.get("/api/suggestions?page=1&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    items = body.get("items") if isinstance(body, dict) else body
    target = [item for item in items if item["id"] == draft_sug["id"]]
    assert target
    assert target[0].get("procurement_snapshot_count", 0) == 0
    assert target[0].get("restock_snapshot_count", 0) == 0
