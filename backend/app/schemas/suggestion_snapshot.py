"""Snapshot-related DTOs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class SnapshotCreateRequest(BaseModel):
    item_ids: list[int] = Field(..., min_length=1)
    note: str | None = Field(default=None, max_length=200)


class SnapshotOut(BaseModel):
    id: int
    suggestion_id: int
    snapshot_type: str
    version: int
    exported_by: int | None = None
    exported_by_name: str | None = None
    exported_at: datetime
    item_count: int
    note: str | None = None
    generation_status: str
    file_size_bytes: int | None = None
    download_count: int

    model_config = {"from_attributes": True}


class SnapshotItemOut(BaseModel):
    id: int
    commodity_sku: str
    commodity_name: str | None = None
    main_image_url: str | None = None
    total_qty: int
    country_breakdown: dict[str, Any]
    warehouse_breakdown: dict[str, Any]
    purchase_qty: int | None = None
    purchase_date: date | None = None
    urgent: bool
    velocity_snapshot: dict[str, Any] | None = None
    sale_days_snapshot: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class SnapshotDetailOut(SnapshotOut):
    items: list[SnapshotItemOut]
    global_config_snapshot: dict[str, Any]
