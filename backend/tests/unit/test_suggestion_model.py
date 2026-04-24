"""Verify Suggestion / SuggestionItem model fields stay aligned."""

from app.models.suggestion import Suggestion, SuggestionItem


def test_suggestion_has_new_archive_fields():
    cols = {c.name for c in Suggestion.__table__.columns}
    assert "archived_by" in cols
    assert "archived_trigger" in cols
    assert "procurement_item_count" in cols
    assert "restock_item_count" in cols
    assert "pushed_items" not in cols
    assert "failed_items" not in cols


def test_suggestion_item_export_fields():
    cols = {c.name for c in SuggestionItem.__table__.columns}
    assert "purchase_qty" in cols
    assert "restock_dates" in cols
    assert "procurement_export_status" in cols
    assert "procurement_exported_snapshot_id" in cols
    assert "procurement_exported_at" in cols
    assert "restock_export_status" in cols
    assert "restock_exported_snapshot_id" in cols
    assert "restock_exported_at" in cols
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
