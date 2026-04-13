"""建议单相关 Pydantic DTO(对应 contracts/suggestion.yaml)。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    pushed_items: int
    failed_items: int
    global_config_snapshot: dict[str, Any]
    created_at: datetime
    archived_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestionItemOut(BaseModel):
    id: int
    commodity_sku: str
    commodity_id: str | None = None
    commodity_name: str | None = None  # 由 API 层 JOIN product_listing 注入
    main_image: str | None = None
    total_qty: int
    country_breakdown: dict[str, Any]
    warehouse_breakdown: dict[str, Any]
    allocation_snapshot: dict[str, AllocationExplanationOut] | None = None
    t_purchase: dict[str, Any]
    velocity_snapshot: dict[str, Any] | None = None
    sale_days_snapshot: dict[str, Any] | None = None
    urgent: bool
    push_blocker: str | None = None
    push_status: str
    saihu_po_number: str | None = None
    push_error: str | None = None
    push_attempt_count: int
    pushed_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestionDetailOut(SuggestionOut):
    items: list[SuggestionItemOut]


class SuggestionListOut(BaseModel):
    items: list[SuggestionOut]
    total: int


class SuggestionItemPatch(BaseModel):
    """编辑建议条目(FR-026 全字段可改 + 非负校验)。"""

    total_qty: int | None = Field(default=None, ge=0)
    country_breakdown: dict[str, int] | None = None
    warehouse_breakdown: dict[str, dict[str, int]] | None = None
    t_purchase: dict[str, str] | None = None  # ISO date strings

    @model_validator(mode="after")
    def _values_non_negative(self) -> "SuggestionItemPatch":
        if self.country_breakdown:
            for k, v in self.country_breakdown.items():
                if v < 0:
                    raise ValueError(f"country_breakdown[{k}] 不可为负")
        if self.warehouse_breakdown:
            for country, wh_dict in self.warehouse_breakdown.items():
                for wid, qty in wh_dict.items():
                    if qty < 0:
                        raise ValueError(
                            f"warehouse_breakdown[{country}][{wid}] 不可为负"
                        )
        return self


class PushRequest(BaseModel):
    """推送选中条目至赛狐。"""

    item_ids: list[int] = Field(..., min_length=1)
