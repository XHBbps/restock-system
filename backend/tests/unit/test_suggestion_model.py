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
    check = [
        c for c in Suggestion.__table_args__
        if getattr(c, "name", "").endswith("status_enum") and hasattr(c, "sqltext")
    ]
    assert len(check) == 1
    sql_text = str(check[0].sqltext)
    assert "draft" in sql_text
    assert "archived" in sql_text
    assert "error" in sql_text
    assert "partial" not in sql_text
    assert "pushed" not in sql_text
