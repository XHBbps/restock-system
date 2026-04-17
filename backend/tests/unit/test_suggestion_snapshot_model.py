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
        if "generation_status_enum" in getattr(c, "name", "")
    ]
    assert len(checks) == 1
    sql = str(checks[0].sqltext)
    assert "generating" in sql and "ready" in sql and "failed" in sql
