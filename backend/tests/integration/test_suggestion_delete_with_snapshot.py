"""DELETE /api/suggestions/{id} 对有 snapshot 的单不可删。"""

import pytest
from sqlalchemy import select

from app.models.global_config import GlobalConfig


@pytest.fixture
async def draft_sug(db_session):
    from app.models.suggestion import Suggestion, SuggestionItem
    sug = Suggestion(
        status="draft",
        global_config_snapshot={"target_days": 30, "buffer_days": 7, "lead_time_days": 14},
        total_items=1,
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
        db_session.add(GlobalConfig(
            id=1,
            login_password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()).decode(),
            suggestion_generation_enabled=True,
        ))
    else:
        gc.suggestion_generation_enabled = True
    await db_session.commit()


@pytest.mark.asyncio
async def test_delete_draft_without_snapshot_ok(client, draft_sug, ensure_gc):
    r = await client.delete(f"/api/suggestions/{draft_sug['id']}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_draft_with_snapshot_rejected(
    client, draft_sug, ensure_gc, tmp_path, monkeypatch
):
    from app import config as cfg_mod
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)
    # 先导出一个 snapshot
    await client.post(
        f"/api/suggestions/{draft_sug['id']}/snapshots",
        json={"item_ids": draft_sug["item_ids"]},
    )
    r = await client.delete(f"/api/suggestions/{draft_sug['id']}")
    assert r.status_code == 409
    text = r.json()["detail"].lower() if isinstance(r.json().get("detail"), str) else ""
    # 允许 message 字段
    body = r.json()
    combined = (text + " " + str(body)).lower()
    assert "snapshot" in combined or "快照" in combined


@pytest.mark.asyncio
async def test_list_includes_snapshot_count(client, draft_sug, ensure_gc):
    r = await client.get("/api/suggestions?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    # 兼容 {items: [...], total: ...} 格式
    items = body.get("items") if isinstance(body, dict) else body
    if items is None:
        items = body
    # 找到 draft_sug
    target = [x for x in items if x["id"] == draft_sug["id"]]
    assert target, f"未找到 draft_sug in {items}"
    assert target[0].get("snapshot_count", 0) == 0
