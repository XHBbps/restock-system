"""Snapshot Excel 多 Sheet 生成工具（纯函数，无 DB 依赖）。"""

from dataclasses import dataclass
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


@dataclass
class SnapshotExportContext:
    """Excel 生成所需的全部数据（由 API 层从 DB 组装）。"""

    suggestion_id: int
    version: int
    exported_at_text: str
    exported_by_name: str | None
    note: str | None
    global_config: dict[str, Any]
    items: list[dict[str, Any]]


HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center")


def _apply_header(ws, row: int, headers: list[str]) -> None:
    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN


def _autosize(ws) -> None:
    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
            value = row[0].value
            if value is None:
                continue
            text = str(value)
            max_len = max(max_len, len(text))
        ws.column_dimensions[letter].width = min(max_len + 2, 50)


def _build_sku_sheet(wb: Workbook, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet("SKU汇总")
    headers = ["SKU", "商品名", "主图 URL", "总采购量", "紧急"]
    _apply_header(ws, 1, headers)
    for item in items:
        ws.append([
            item["commodity_sku"],
            item.get("commodity_name") or "",
            item.get("main_image_url") or "",
            item["total_qty"],
            "是" if item["urgent"] else "",
        ])
    _autosize(ws)


def _build_sku_country_sheet(wb: Workbook, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet("SKU×国家")
    headers = ["SKU", "商品名", "国家", "补货量", "可售天数", "日均销量"]
    _apply_header(ws, 1, headers)
    for item in items:
        velocity = item.get("velocity_snapshot") or {}
        sale_days = item.get("sale_days_snapshot") or {}
        for country, qty in item["country_breakdown"].items():
            ws.append([
                item["commodity_sku"],
                item.get("commodity_name") or "",
                country,
                qty,
                sale_days.get(country),
                velocity.get(country),
            ])
    _autosize(ws)


def _build_sku_country_warehouse_sheet(wb: Workbook, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet("SKU×国家×仓库")
    headers = ["SKU", "商品名", "国家", "仓库 ID", "仓库名", "分配量"]
    _apply_header(ws, 1, headers)
    for item in items:
        wh_name_map = item.get("warehouse_name_map") or {}
        for country, wh_dict in item["warehouse_breakdown"].items():
            for wh_id, qty in wh_dict.items():
                ws.append([
                    item["commodity_sku"],
                    item.get("commodity_name") or "",
                    country,
                    wh_id,
                    wh_name_map.get(wh_id, ""),
                    qty,
                ])
    _autosize(ws)


def _build_meta_sheet(wb: Workbook, ctx: SnapshotExportContext) -> None:
    ws = wb.create_sheet("导出元信息")
    total_qty_sum = sum(item["total_qty"] for item in ctx.items)
    rows: list[tuple[str, Any]] = [
        ("建议单 ID", ctx.suggestion_id),
        ("快照版本", f"v{ctx.version}"),
        ("导出时间", ctx.exported_at_text),
        ("导出人", ctx.exported_by_name or "系统"),
        ("批次备注", ctx.note or ""),
        ("", ""),
        ("—— 全局参数（导出时冻结）——", ""),
        ("target_days", ctx.global_config.get("target_days", "")),
        ("buffer_days", ctx.global_config.get("buffer_days", "")),
        ("lead_time_days", ctx.global_config.get("lead_time_days", "")),
        ("restock_regions", ", ".join(ctx.global_config.get("restock_regions") or [])),
        ("", ""),
        ("总 SKU 数", len(ctx.items)),
        ("总补货量", total_qty_sum),
    ]
    for key, value in rows:
        ws.append([key, value])
    for row_idx in [1, 7]:
        ws.cell(row=row_idx, column=1).font = Font(bold=True)
    _autosize(ws)


def build_excel_workbook(ctx: SnapshotExportContext) -> Workbook:
    """组装完整 4-Sheet 工作簿。"""
    wb = Workbook()
    default = wb.active
    if default is not None:
        wb.remove(default)
    _build_sku_sheet(wb, ctx.items)
    _build_sku_country_sheet(wb, ctx.items)
    _build_sku_country_warehouse_sheet(wb, ctx.items)
    _build_meta_sheet(wb, ctx)
    return wb


def build_filename(suggestion_id: int, version: int, exported_at_compact: str) -> str:
    """生成 '补货建议-{sid}-v{ver}-{YYYYMMDD-HHmmss}.xlsx'。"""
    return f"补货建议-{suggestion_id}-v{version}-{exported_at_compact}.xlsx"
