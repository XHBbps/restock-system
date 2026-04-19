"""Snapshot 相关 Pydantic DTO。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SnapshotCreateRequest(BaseModel):
    """POST /api/suggestions/{id}/snapshots 请求体。"""

    item_ids: list[int] = Field(..., min_length=1)
    note: str | None = Field(default=None, max_length=200)


class SnapshotOut(BaseModel):
    """Snapshot 摘要（用于列表）。"""

    id: int
    suggestion_id: int
    version: int
    exported_by: int | None = None
    exported_by_name: str | None = None  # 由 API 层 JOIN sys_user 注入
    exported_at: datetime
    item_count: int
    note: str | None = None
    generation_status: str  # 'generating' | 'ready' | 'failed'
    file_size_bytes: int | None = None
    download_count: int

    model_config = {"from_attributes": True}


class SnapshotItemOut(BaseModel):
    """Snapshot 内冻结 item。"""

    id: int
    commodity_sku: str
    commodity_name: str | None = None
    main_image_url: str | None = None
    total_qty: int
    country_breakdown: dict[str, Any]
    warehouse_breakdown: dict[str, Any]
    urgent: bool
    velocity_snapshot: dict[str, Any] | None = None
    sale_days_snapshot: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class SnapshotDetailOut(SnapshotOut):
    """Snapshot 详情（含所有 items）。"""

    items: list[SnapshotItemOut]
    global_config_snapshot: dict[str, Any]
