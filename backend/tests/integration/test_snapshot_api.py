"""Snapshot API 集成测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.global_config import GlobalConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot


@pytest.fixture
async def seed_suggestion(db_session):
    """draft 建议单 + 3 个 item。"""
    sug = Suggestion(
        status="draft",
        global_config_snapshot={
            "target_days": 30,
            "buffer_days": 7,
            "lead_time_days": 14,
        },
        total_items=3,
        triggered_by="manual",
    )
    db_session.add(sug)
    await db_session.flush()
    items = [
        SuggestionItem(
            suggestion_id=sug.id,
            commodity_sku=f"SKU-SNAPTEST-{i}",
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
    await db_session.flush()
    # 必须 commit，使 client fixture 内独立 session 可见
    await db_session.commit()
    return {
        "suggestion_id": sug.id,
        "item_ids": [it.id for it in items],
    }


@pytest.fixture
async def ensure_global_config(db_session):
    """确保 global_config id=1 存在 + 开关 ON。"""
    existing = (
        await db_session.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    if existing is None:
        import bcrypt

        gc = GlobalConfig(
            id=1,
            login_password_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode(),
            suggestion_generation_enabled=True,
        )
        db_session.add(gc)
    else:
        existing.suggestion_generation_enabled = True
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_snapshot_success(
    client, seed_suggestion, ensure_global_config, tmp_path, monkeypatch
):
    # 把 export 目录重定向到 tmp_path
    from app import config as cfg_mod

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    r = await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:2], "note": "test export"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["item_count"] == 2
    assert body["generation_status"] == "ready"
    assert body["note"] == "test export"
    assert body["file_size_bytes"] and body["file_size_bytes"] > 0


@pytest.mark.asyncio
async def test_create_snapshot_version_increments(
    client, seed_suggestion, ensure_global_config, tmp_path, monkeypatch
):
    from app import config as cfg_mod

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    r1 = await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )
    r2 = await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[1:2]},
    )
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_create_snapshot_marks_items_exported(
    client, seed_suggestion, ensure_global_config, db_session, tmp_path, monkeypatch
):
    from app import config as cfg_mod

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    await client.post(
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


@pytest.mark.asyncio
async def test_create_snapshot_excel_failure_keeps_items_pending_and_allows_retry(
    client, seed_suggestion, ensure_global_config, db_session, tmp_path, monkeypatch
):
    from app import config as cfg_mod
    from app.api import snapshot as snapshot_api

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    class _FailingWorkbook:
        def save(self, _target_path):
            raise RuntimeError("disk full")

    original_builder = snapshot_api.build_excel_workbook
    monkeypatch.setattr(snapshot_api, "build_excel_workbook", lambda _ctx: _FailingWorkbook())

    sid = seed_suggestion["suggestion_id"]
    item_id = seed_suggestion["item_ids"][0]
    failed_resp = await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": [item_id]},
    )
    assert failed_resp.status_code == 500

    db_session.expire_all()
    item_after_failure = (
        await db_session.execute(select(SuggestionItem).where(SuggestionItem.id == item_id))
    ).scalar_one()
    failed_snapshot = (
        await db_session.execute(
            select(SuggestionSnapshot).where(SuggestionSnapshot.suggestion_id == sid)
        )
    ).scalar_one()
    assert item_after_failure.export_status == "pending"
    assert failed_snapshot.generation_status == "failed"

    monkeypatch.setattr(snapshot_api, "build_excel_workbook", original_builder)
    retry_resp = await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": [item_id]},
    )
    assert retry_resp.status_code == 201, retry_resp.text
    assert retry_resp.json()["version"] == 2

    db_session.expire_all()
    item_after_retry = (
        await db_session.execute(select(SuggestionItem).where(SuggestionItem.id == item_id))
    ).scalar_one()
    assert item_after_retry.export_status == "exported"


@pytest.mark.asyncio
async def test_create_snapshot_flips_toggle_off(
    client, seed_suggestion, ensure_global_config, db_session, tmp_path, monkeypatch
):
    from app import config as cfg_mod

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    # 前置：ON
    gc_before = (
        await db_session.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one()
    assert gc_before.suggestion_generation_enabled is True

    await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )

    # 开关 OFF
    await db_session.refresh(gc_before)
    assert gc_before.suggestion_generation_enabled is False


@pytest.mark.asyncio
async def test_list_snapshots_for_suggestion(
    client, seed_suggestion, ensure_global_config, tmp_path, monkeypatch
):
    from app import config as cfg_mod
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": item_ids[:1]},
    )
    r = await client.get(f"/api/suggestions/{sid}/snapshots")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["version"] == 1


@pytest.mark.asyncio
async def test_snapshot_detail(
    client, seed_suggestion, ensure_global_config, tmp_path, monkeypatch
):
    from app import config as cfg_mod
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots",
            json={"item_ids": item_ids[:2]},
        )
    ).json()
    snap_id = created["id"]
    r = await client.get(f"/api/snapshots/{snap_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_snapshot_download(
    client, seed_suggestion, ensure_global_config, tmp_path, monkeypatch
):
    from app import config as cfg_mod
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(tmp_path), raising=False)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots",
            json={"item_ids": item_ids[:1]},
        )
    ).json()
    snap_id = created["id"]

    r1 = await client.get(f"/api/snapshots/{snap_id}/download")
    assert r1.status_code == 200
    assert "attachment" in r1.headers.get("content-disposition", "")

    # download_count 递增
    r2 = await client.get(f"/api/snapshots/{snap_id}")
    assert r2.json()["download_count"] == 1


@pytest.mark.asyncio
async def test_snapshot_download_404(client, ensure_global_config):
    r = await client.get("/api/snapshots/99999/download")
    assert r.status_code == 404
