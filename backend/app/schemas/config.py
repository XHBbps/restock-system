"""配置相关 Pydantic DTO(contracts/config.yaml)。"""

from typing import Literal

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator


# ==================== Global Config ====================
class GlobalConfigOut(BaseModel):
    buffer_days: int
    target_days: int
    lead_time_days: int
    sync_interval_minutes: int
    scheduler_enabled: bool
    calc_enabled: bool
    calc_cron: str
    default_purchase_warehouse_id: str | None = None
    include_tax: Literal["0", "1"]
    shop_sync_mode: Literal["all", "specific"]

    model_config = {"from_attributes": True}


class GlobalConfigPatch(BaseModel):
    buffer_days: int | None = Field(default=None, ge=1, le=365)
    target_days: int | None = Field(default=None, ge=1, le=365)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    sync_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    scheduler_enabled: bool | None = None
    calc_enabled: bool | None = None
    calc_cron: str | None = None
    default_purchase_warehouse_id: str | None = None
    include_tax: Literal["0", "1"] | None = None
    shop_sync_mode: Literal["all", "specific"] | None = None

    @field_validator("calc_cron")
    @classmethod
    def validate_calc_cron(cls, value: str | None) -> str | None:
        if value is None:
            return None
        CronTrigger.from_crontab(value)
        return value


# ==================== SKU Config ====================
class SkuConfigOut(BaseModel):
    commodity_sku: str
    enabled: bool
    lead_time_days: int | None = None
    commodity_name: str | None = None
    main_image: str | None = None

    model_config = {"from_attributes": True}


class SkuConfigListOut(BaseModel):
    items: list[SkuConfigOut]
    total: int


class SkuConfigPatch(BaseModel):
    enabled: bool | None = None
    lead_time_days: int | None = Field(default=None, ge=0, le=365)


# ==================== Warehouse ====================
class WarehouseOut(BaseModel):
    id: str
    name: str
    type: int
    country: str | None = None
    replenish_site_raw: str | None = None

    model_config = {"from_attributes": True}


class WarehouseCountryPatch(BaseModel):
    country: str = Field(..., min_length=2, max_length=2, description="ISO 二字码")


# ==================== Zipcode Rule ====================
class ZipcodeRuleIn(BaseModel):
    country: str = Field(..., min_length=2, max_length=2)
    prefix_length: int = Field(..., ge=1, le=10)
    value_type: Literal["number", "string"]
    operator: Literal["=", "!=", ">", ">=", "<", "<="]
    compare_value: str = Field(..., min_length=1, max_length=50)
    warehouse_id: str
    priority: int = Field(default=100, ge=1)


class ZipcodeRuleOut(ZipcodeRuleIn):
    id: int

    model_config = {"from_attributes": True}


# ==================== Shop ====================
class ShopOut(BaseModel):
    id: str
    name: str
    seller_id: str | None = None
    region: str | None = None
    marketplace_id: str | None = None
    status: str
    sync_enabled: bool

    model_config = {"from_attributes": True}


class ShopPatch(BaseModel):
    sync_enabled: bool
