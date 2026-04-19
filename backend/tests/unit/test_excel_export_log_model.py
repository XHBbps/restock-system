from app.models.excel_export_log import ExcelExportLog


def test_excel_export_log_fields():
    cols = {c.name for c in ExcelExportLog.__table__.columns}
    expected = {
        "id", "snapshot_id", "action",
        "performed_by", "performed_at",
        "performed_from_ip", "user_agent",
    }
    assert expected.issubset(cols)


def test_action_enum():
    checks = [
        c for c in ExcelExportLog.__table_args__
        if "action_enum" in getattr(c, "name", "")
    ]
    assert len(checks) == 1
    sql = str(checks[0].sqltext)
    assert "generate" in sql and "download" in sql
