from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from openpyxl import Workbook, load_workbook

from app.services.order_edit import (
    apply_order_info_match,
    build_template_workbook,
    parse_requested_fields,
    preview_order_info_match,
)

BEIJING = ZoneInfo("Asia/Shanghai")


class _ScalarsWrapper:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _RowsResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values

    def scalars(self):
        return _ScalarsWrapper(self._values)


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.committed = False
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if not self.responses:
            return _RowsResult([])
        return self.responses.pop(0)

    async def commit(self):
        self.committed = True


def _workbook_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def _base_parse_responses(extra=None):
    return [
        _RowsResult([("SHOP-1", "Main Shop")]),
        _RowsResult(["Amazon"]),
        _RowsResult(["US"]),
        _RowsResult([]),
        _RowsResult(["ORDER-1"]),
        *(extra or []),
    ]


def test_parse_requested_fields_accepts_keys_and_labels() -> None:
    fields = parse_requested_fields("shop_name,国家")

    assert [field.key for field in fields] == ["shop_name", "country_code"]


def test_build_template_workbook_has_exact_header_order() -> None:
    fields = parse_requested_fields("shop_name,country_code")
    workbook = load_workbook(build_template_workbook(fields))

    assert [cell.value for cell in workbook.active[1]] == ["订单号", "店铺名称", "国家"]


@pytest.mark.asyncio
async def test_preview_order_info_match_reports_duplicate_and_missing_order() -> None:
    content = _workbook_bytes(
        ["订单号", "店铺名称", "国家"],
        [
            ["ORDER-1", "Main Shop", "US"],
            ["ORDER-1", "Main Shop", "US"],
            ["ORDER-404", "Main Shop", "US"],
        ],
    )
    db = _FakeSession(_base_parse_responses())

    result = await preview_order_info_match(
        db,  # type: ignore[arg-type]
        fields=parse_requested_fields("shop_name,country_code"),
        content=content,
    )

    assert result.matched_order_count == 0
    assert [error.row for error in result.errors] == [3, 4]
    assert "重复" in result.errors[0].message
    assert result.errors[1].message == "订单号不存在"


@pytest.mark.asyncio
async def test_apply_order_info_match_updates_all_packages_and_sets_manual_lock() -> None:
    header_1 = SimpleNamespace(manual_edit_fields=None)
    header_2 = SimpleNamespace(manual_edit_fields=["postal_code"])
    content = _workbook_bytes(
        ["订单号", "店铺名称", "国家", "订单金额", "下单时间"],
        [["ORDER-1", "SHOP-1", "US", "12.34", "2026-05-09 10:11:12"]],
    )
    db = _FakeSession(_base_parse_responses(extra=[_RowsResult([header_1, header_2])]))

    result = await apply_order_info_match(
        db,  # type: ignore[arg-type]
        fields=parse_requested_fields("shop_name,country_code,order_total_amount,purchase_date"),
        content=content,
        user_id=7,
    )

    assert result.updated_order_count == 2
    assert db.committed is True
    for header in (header_1, header_2):
        assert header.manual_edit_locked is True
        assert header.manual_edited_by == 7
        assert header.shop_name == "Main Shop"
        assert header.country_code == "US"
        assert header.order_total_amount == Decimal("12.34")
        assert header.purchase_date == datetime(2026, 5, 9, 10, 11, 12, tzinfo=BEIJING)
    assert header_2.manual_edit_fields == [
        "country_code",
        "order_total_amount",
        "postal_code",
        "purchase_date",
        "shop_name",
    ]
