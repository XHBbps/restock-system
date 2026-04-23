"""Suggestion-related DTOs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SuggestionDisplayStatusCode = Literal["pending", "exported", "archived", "error"]


class AllocationExplanationOut(BaseModel):
    allocation_mode: str
    matched_order_qty: int
    unknown_order_qty: int
    eligible_warehouses: list[str]


class SuggestionOut(BaseModel):
    id: int
    status: str
    triggered_by: str
    total_items: int
    procurement_item_count: int = 0
    restock_item_count: int = 0
    procurement_snapshot_count: int = 0
    restock_snapshot_count: int = 0
    archived_trigger: str | None = None
    # 派生状态，供历史页直接展示（未导出 / 已导出 / 已归档）
    procurement_display_status: str = "未导出"
    restock_display_status: str = "未导出"
    # 机器可读的状态码，供前端按 code 映射 tag 色 / i18n（label 保留 UX 兼容）
    procurement_display_status_code: SuggestionDisplayStatusCode = "pending"
    restock_display_status_code: SuggestionDisplayStatusCode = "pending"
    global_config_snapshot: dict[str, Any]
    created_at: datetime
    archived_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestionItemOut(BaseModel):
    id: int
    commodity_sku: str
    commodity_name: str | None = None
    main_image: str | None = None
    total_qty: int
    country_breakdown: dict[str, Any]
    warehouse_breakdown: dict[str, Any]
    restock_dates: dict[str, str | None] = Field(default_factory=dict)
    allocation_snapshot: dict[str, AllocationExplanationOut] | None = None
    velocity_snapshot: dict[str, Any] | None = None
    sale_days_snapshot: dict[str, Any] | None = None
    urgent: bool
    purchase_qty: int
    purchase_date: date | None = None
    procurement_export_status: str
    procurement_exported_snapshot_id: int | None = None
    procurement_exported_at: datetime | None = None
    restock_export_status: str
    restock_exported_snapshot_id: int | None = None
    restock_exported_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestionDetailOut(SuggestionOut):
    items: list[SuggestionItemOut]


class SuggestionListOut(BaseModel):
    items: list[SuggestionOut]
    total: int
    page: int
    page_size: int


class SuggestionItemPatch(BaseModel):
    total_qty: int | None = Field(default=None, ge=0)
    purchase_qty: int | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    country_breakdown: dict[str, int] | None = None
    warehouse_breakdown: dict[str, dict[str, int]] | None = None

    @model_validator(mode="after")
    def _values_non_negative(self) -> SuggestionItemPatch:
        if self.country_breakdown:
            for country, qty in self.country_breakdown.items():
                if qty < 0:
                    raise ValueError(f"country_breakdown[{country}] 不可为负")
        if self.warehouse_breakdown:
            for country, warehouse_map in self.warehouse_breakdown.items():
                for warehouse_id, qty in warehouse_map.items():
                    if qty < 0:
                        raise ValueError(f"warehouse_breakdown[{country}][{warehouse_id}] 不可为负")
        return self
