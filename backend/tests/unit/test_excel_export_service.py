"""Excel 导出服务单测（无 DB）。"""

import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.services.excel_export import SnapshotExportContext, build_excel_workbook, build_filename


@pytest.fixture
def sample_context() -> SnapshotExportContext:
    return SnapshotExportContext(
        suggestion_id=42,
        version=1,
        exported_at_text="2026-04-17 14:30:52",
        exported_by_name="alice",
        note="发给 A 供应商",
        global_config={
            "target_days": 30,
            "buffer_days": 7,
            "lead_time_days": 14,
            "restock_regions": ["US", "GB"],
        },
        items=[
            {
                "commodity_sku": "SKU-A",
                "commodity_name": "商品 A",
                "main_image_url": "https://img/a.jpg",
                "total_qty": 150,
                "urgent": True,
                "country_breakdown": {"US": 100, "GB": 50},
                "warehouse_breakdown": {"US": {"WH-1": 60, "WH-2": 40}, "GB": {"WH-5": 50}},
                "velocity_snapshot": {"US": 1.5, "GB": 0.8},
                "sale_days_snapshot": {"US": 20, "GB": 40},
                "warehouse_name_map": {"WH-1": "加州仓", "WH-2": "纽约仓", "WH-5": "伦敦仓"},
            }
        ],
    )


def test_workbook_has_four_sheets(sample_context):
    wb = build_excel_workbook(sample_context)
    assert wb.sheetnames == ["SKU汇总", "SKU×国家", "SKU×国家×仓库", "导出元信息"]


def test_sku_sheet_rows(sample_context):
    wb = build_excel_workbook(sample_context)
    ws = wb["SKU汇总"]
    assert ws.max_row == 2
    header = [c.value for c in ws[1]]
    assert "SKU" in header and "总采购量" in header and "紧急" in header
    row = [c.value for c in ws[2]]
    assert row[header.index("SKU")] == "SKU-A"
    assert row[header.index("总采购量")] == 150


def test_sku_country_sheet_rows(sample_context):
    wb = build_excel_workbook(sample_context)
    ws = wb["SKU×国家"]
    assert ws.max_row == 3  # 表头 + 2 国家


def test_sku_country_warehouse_sheet_rows(sample_context):
    wb = build_excel_workbook(sample_context)
    ws = wb["SKU×国家×仓库"]
    assert ws.max_row == 4  # 表头 + US 2 仓 + GB 1 仓


def test_meta_sheet_content(sample_context):
    wb = build_excel_workbook(sample_context)
    ws = wb["导出元信息"]
    kv = {row[0].value: row[1].value for row in ws.iter_rows(min_row=1, max_row=ws.max_row)}
    assert kv["建议单 ID"] == 42
    assert kv["快照版本"] == "v1"
    assert kv["导出人"] == "alice"
    assert kv["批次备注"] == "发给 A 供应商"


def test_workbook_writes_to_disk(tmp_path, sample_context):
    wb = build_excel_workbook(sample_context)
    target = tmp_path / "test.xlsx"
    wb.save(target)
    assert target.exists()
    assert target.stat().st_size > 0
    wb2 = load_workbook(target)
    assert "SKU汇总" in wb2.sheetnames


def test_filename_format():
    name = build_filename(suggestion_id=42, version=1, exported_at_compact="20260417-143052")
    assert name == "补货建议-42-v1-20260417-143052.xlsx"
