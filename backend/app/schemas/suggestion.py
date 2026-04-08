"""建议单相关 Pydantic DTO（对应 contracts/suggestion.yaml）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    t_purchase: dict[str, Any]
    t_ship: dict[str, Any]
    overstock_countries: list[str]
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
    """编辑建议条目（FR-026 全字段可改 + 非负校验）。"""

    total_qty: int | None = Field(default=None, ge=0)
    country_breakdown: dict[str, int] | None = None
    warehouse_breakdown: dict[str, dict[str, int]] | None = None
    t_purchase: dict[str, str] | None = None  # ISO date strings
    t_ship: dict[str, str] | None = None


class PushRequest(BaseModel):
    """推送选中条目至赛狐（FR-045a 上限 50）。"""

    item_ids: list[int] = Field(..., min_length=1, max_length=50)
