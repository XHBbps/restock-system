"""Snapshot API integration tests for split procurement/restock exports."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.global_config import GlobalConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot


def _set_export_dir(monkeypatch) -> None:
    from app import config as cfg_mod

    export_dir = Path("backend/.test_exports").resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "export_storage_dir", str(export_dir), raising=False)


@pytest.fixture
async def seed_suggestion(db_session):
    sug = Suggestion(
        status="draft",
        global_config_snapshot={
            "target_days": 30,
            "buffer_days": 7,
            "lead_time_days": 14,
            "safety_stock_days": 15,
        },
        total_items=3,
        procurement_item_count=3,
        restock_item_count=3,
        triggered_by="manual",
    )
    db_session.add(sug)
    await db_session.flush()
    items = [
        SuggestionItem(
            suggestion_id=sug.id,
            commodity_sku=f"SKU-SNAPTEST-{i}",
            total_qty=100 + i,
            purchase_qty=20 + i,
            country_breakdown={"US": 50 + i, "GB": 50},
            warehouse_breakdown={"US": {"WH-1": 50 + i}, "GB": {"WH-5": 50}},
            restock_dates={"US": "2026-04-21", "GB": "2026-05-01"},
            urgent=(i % 2 == 0),
            velocity_snapshot={"US": 1.5, "GB": 0.8},
            sale_days_snapshot={"US": 20, "GB": 40},
        )
        for i in range(3)
    ]
    db_session.add_all(items)
    await db_session.flush()
    await db_session.commit()
    return {
        "suggestion_id": sug.id,
        "item_ids": [it.id for it in items],
    }


@pytest.fixture
async def ensure_global_config(db_session):
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
async def test_old_snapshot_endpoint_gone(client, seed_suggestion, ensure_global_config):
    sid = seed_suggestion["suggestion_id"]

    resp = await client.post(
        f"/api/suggestions/{sid}/snapshots",
        json={"item_ids": seed_suggestion["item_ids"][:1]},
    )

    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_create_procurement_snapshot_success(
    client, seed_suggestion, ensure_global_config, monkeypatch
):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    resp = await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
        json={"item_ids": item_ids[:2], "note": "test export"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["snapshot_type"] == "procurement"
    assert body["version"] == 1
    assert body["item_count"] == 2
    assert body["generation_status"] == "ready"
    assert body["note"] == "test export"
    assert body["file_size_bytes"] and body["file_size_bytes"] > 0


@pytest.mark.asyncio
async def test_snapshot_version_increments_by_type(
    client, seed_suggestion, ensure_global_config, monkeypatch
):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    p1 = await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
        json={"item_ids": item_ids[:1]},
    )
    r1 = await client.post(
        f"/api/suggestions/{sid}/snapshots/restock",
        json={"item_ids": item_ids[1:2]},
    )
    p2 = await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
        json={"item_ids": item_ids[2:3]},
    )
    assert p1.json()["version"] == 1
    assert r1.json()["version"] == 1
    assert p2.json()["version"] == 2


@pytest.mark.asyncio
async def test_create_snapshot_marks_items_exported(
    client, seed_suggestion, ensure_global_config, db_session, monkeypatch
):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
        json={"item_ids": item_ids[:2]},
    )
    await client.post(
        f"/api/suggestions/{sid}/snapshots/restock",
        json={"item_ids": item_ids[1:3]},
    )
    rows = (
        await db_session.execute(
            select(
                SuggestionItem.id,
                SuggestionItem.procurement_export_status,
                SuggestionItem.restock_export_status,
            ).where(SuggestionItem.suggestion_id == sid)
        )
    ).all()
    status_map = {row[0]: (row[1], row[2]) for row in rows}
    assert status_map[item_ids[0]] == ("exported", "pending")
    assert status_map[item_ids[1]] == ("exported", "exported")
    assert status_map[item_ids[2]] == ("pending", "exported")


@pytest.mark.asyncio
async def test_create_snapshot_excel_failure_keeps_items_pending_and_allows_retry(
    client, seed_suggestion, ensure_global_config, db_session, monkeypatch
):
    from app.api import snapshot as snapshot_api

    _set_export_dir(monkeypatch)

    class _FailingWorkbook:
        def save(self, _target_path):
            raise RuntimeError("disk full")

    original_builder = snapshot_api.build_procurement_workbook
    monkeypatch.setattr(snapshot_api, "build_procurement_workbook", lambda _ctx: _FailingWorkbook())

    sid = seed_suggestion["suggestion_id"]
    item_id = seed_suggestion["item_ids"][0]
    failed_resp = await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
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
    assert item_after_failure.procurement_export_status == "pending"
    assert failed_snapshot.generation_status == "failed"

    monkeypatch.setattr(snapshot_api, "build_procurement_workbook", original_builder)
    retry_resp = await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
        json={"item_ids": [item_id]},
    )
    assert retry_resp.status_code == 201, retry_resp.text
    assert retry_resp.json()["version"] == 2

    db_session.expire_all()
    item_after_retry = (
        await db_session.execute(select(SuggestionItem).where(SuggestionItem.id == item_id))
    ).scalar_one()
    assert item_after_retry.procurement_export_status == "exported"


@pytest.mark.asyncio
async def test_create_snapshot_does_not_flip_toggle_off(
    client, seed_suggestion, ensure_global_config, db_session, monkeypatch
):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    gc_before = (
        await db_session.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one()
    assert gc_before.suggestion_generation_enabled is True

    await client.post(
        f"/api/suggestions/{sid}/snapshots/restock",
        json={"item_ids": item_ids[:1]},
    )

    await db_session.refresh(gc_before)
    assert gc_before.suggestion_generation_enabled is True


@pytest.mark.asyncio
async def test_list_snapshots_for_suggestion_filters_by_type(
    client, seed_suggestion, ensure_global_config, monkeypatch
):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    await client.post(
        f"/api/suggestions/{sid}/snapshots/procurement",
        json={"item_ids": item_ids[:1]},
    )
    await client.post(
        f"/api/suggestions/{sid}/snapshots/restock",
        json={"item_ids": item_ids[:1]},
    )
    resp = await client.get(f"/api/suggestions/{sid}/snapshots?type=procurement")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["snapshot_type"] == "procurement"
    assert body[0]["version"] == 1


@pytest.mark.asyncio
async def test_snapshot_detail(client, seed_suggestion, ensure_global_config, monkeypatch):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots/procurement",
            json={"item_ids": item_ids[:2]},
        )
    ).json()
    snap_id = created["id"]
    resp = await client.get(f"/api/snapshots/{snap_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot_type"] == "procurement"
    assert len(body["items"]) == 2
    assert body["items"][0]["purchase_qty"] is not None
    assert "purchase_date" not in body["items"][0]
    assert body["items"][0]["restock_dates"]["US"] == "2026-04-21"


@pytest.mark.asyncio
async def test_restock_snapshot_freezes_restock_dates(
    client, seed_suggestion, ensure_global_config, db_session, monkeypatch
):
    from app.models.suggestion_snapshot import SuggestionSnapshotItem

    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots/restock",
            json={"item_ids": item_ids[:1]},
        )
    ).json()

    snapshot_item = (
        await db_session.execute(
            select(SuggestionSnapshotItem).where(SuggestionSnapshotItem.snapshot_id == created["id"])
        )
    ).scalar_one()
    assert snapshot_item.restock_dates["US"] == "2026-04-21"


@pytest.mark.asyncio
async def test_snapshot_download(client, seed_suggestion, ensure_global_config, monkeypatch):
    _set_export_dir(monkeypatch)

    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots/restock",
            json={"item_ids": item_ids[:1]},
        )
    ).json()
    snap_id = created["id"]

    r1 = await client.get(f"/api/snapshots/{snap_id}/download")
    assert r1.status_code == 200
    assert "attachment" in r1.headers.get("content-disposition", "")

    r2 = await client.get(f"/api/snapshots/{snap_id}")
    assert r2.json()["download_count"] == 1


@pytest.mark.asyncio
async def test_snapshot_download_404(client, ensure_global_config):
    resp = await client.get("/api/snapshots/99999/download")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_snapshot_download_410_when_file_missing_without_purged_log(
    client, seed_suggestion, ensure_global_config, db_session, monkeypatch
):
    """文件不在磁盘 + excel_export_log 未标记 purged → 410 "文件已丢失"。"""
    from app.config import get_settings
    from app.models.suggestion_snapshot import SuggestionSnapshot

    _set_export_dir(monkeypatch)
    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots/restock",
            json={"item_ids": item_ids[:1]},
        )
    ).json()
    snap_id = created["id"]

    snapshot = (
        await db_session.execute(select(SuggestionSnapshot).where(SuggestionSnapshot.id == snap_id))
    ).scalar_one()
    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    file_abs = storage_root / (snapshot.file_path or "")
    if file_abs.exists():
        file_abs.unlink()

    resp = await client.get(f"/api/snapshots/{snap_id}/download")
    assert resp.status_code == 410
    assert resp.json()["detail"] == "文件已丢失"


@pytest.mark.asyncio
async def test_snapshot_download_410_with_purged_log_shows_retention_message(
    client, seed_suggestion, ensure_global_config, db_session, monkeypatch
):
    """retention 已标记 file_purged_at → 410 带"已过期清理"明确提示。"""
    from sqlalchemy import update

    from app.config import get_settings
    from app.core.timezone import now_beijing
    from app.models.excel_export_log import ExcelExportLog
    from app.models.suggestion_snapshot import SuggestionSnapshot

    _set_export_dir(monkeypatch)
    sid = seed_suggestion["suggestion_id"]
    item_ids = seed_suggestion["item_ids"]
    created = (
        await client.post(
            f"/api/suggestions/{sid}/snapshots/restock",
            json={"item_ids": item_ids[:1]},
        )
    ).json()
    snap_id = created["id"]

    snapshot = (
        await db_session.execute(select(SuggestionSnapshot).where(SuggestionSnapshot.id == snap_id))
    ).scalar_one()
    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    file_abs = storage_root / (snapshot.file_path or "")
    if file_abs.exists():
        file_abs.unlink()

    # 模拟 retention_purge 标记：写入 excel_export_log.file_purged_at
    await db_session.execute(
        update(ExcelExportLog)
        .where(ExcelExportLog.snapshot_id == snap_id)
        .where(ExcelExportLog.action == "generate")
        .values(file_purged_at=now_beijing())
    )
    await db_session.commit()

    resp = await client.get(f"/api/snapshots/{snap_id}/download")
    assert resp.status_code == 410
    detail = resp.json()["detail"]
    assert "已过期清理" in detail
    assert str(settings.retention_exports_days) in detail
