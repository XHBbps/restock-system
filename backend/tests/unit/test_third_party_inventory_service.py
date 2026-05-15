from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from app.core.exceptions import ValidationFailed
from app.services.third_party_inventory import parse_third_party_inventory_workbook


def _workbook_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_parse_third_party_inventory_workbook_accepts_required_columns() -> None:
    rows = parse_third_party_inventory_workbook(
        _workbook_bytes(
            ["仓库", "SKU", "可用数", "待出库", "忽略列"],
            [["US 3PL", "SKU-1", 10, 2, "x"], ["US 3PL", "SKU-1", 3, 1, None]],
        )
    )

    assert len(rows) == 2
    assert rows[0].warehouse_name == "US 3PL"
    assert rows[0].commodity_sku == "SKU-1"
    assert rows[0].available == 10
    assert rows[0].reserved == 2
    assert rows[0].error_message is None


def test_parse_third_party_inventory_workbook_records_invalid_rows() -> None:
    rows = parse_third_party_inventory_workbook(
        _workbook_bytes(
            ["仓库", "SKU", "可用数", "待出库"],
            [["", "SKU-1", 1, 0], ["US 3PL", "", 1, 0], ["US 3PL", "SKU-2", -1, "x"]],
        )
    )

    assert [row.source_row_no for row in rows] == [2, 3, 4]
    assert "仓库不能为空" in (rows[0].error_message or "")
    assert "SKU 不能为空" in (rows[1].error_message or "")
    assert "可用数 必须为非负整数" in (rows[2].error_message or "")
    assert "待出库 必须为非负整数" in (rows[2].error_message or "")


def test_parse_third_party_inventory_workbook_requires_headers() -> None:
    with pytest.raises(ValidationFailed, match="缺少必要列"):
        parse_third_party_inventory_workbook(
            _workbook_bytes(["仓库", "SKU", "可用数"], [["US 3PL", "SKU-1", 1]])
        )
