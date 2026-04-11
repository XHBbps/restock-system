"""配置相关 Pydantic DTO(contracts/config.yaml)。"""

from typing import Literal

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


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
    total_stock: int = 0

    model_config = {"from_attributes": True}


class WarehouseCountryPatch(BaseModel):
    country: str | None = Field(default=None, min_length=2, max_length=2, description="ISO 二字码或 null 清除")


# ==================== Zipcode Rule ====================
class ZipcodeRuleIn(BaseModel):
    country: str = Field(..., min_length=2, max_length=2)
    prefix_length: int = Field(..., ge=1, le=10)
    value_type: Literal["number", "string"]
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "contains", "not_contains"]
    compare_value: str = Field(..., min_length=1, max_length=50)
    warehouse_id: str
    priority: int = Field(default=100, ge=1)

    @field_validator("compare_value")
    @classmethod
    def validate_compare_value(cls, value: str, info: ValidationInfo) -> str:
        compare_value = value.strip()
        if not compare_value:
            raise ValueError("compare_value 不能为空")

        operator = info.data.get("operator")
        value_type = info.data.get("value_type")
        if value_type == "number":
            try:
                float(compare_value)
            except (TypeError, ValueError) as exc:
                raise ValueError("数字类型的 compare_value 必须是有效数字") from exc
        if value_type == "string" and operator in {"contains", "not_contains"}:
            tokens = [item.strip() for item in compare_value.split(",") if item.strip()]
            if not tokens:
                raise ValueError("包含/不包含规则至少需要一个有效比较值")
        return compare_value

    @model_validator(mode="after")
    def validate_operator_by_value_type(self) -> "ZipcodeRuleIn":
        string_operators = {"=", "!=", "contains", "not_contains"}
        number_operators = {"=", "!=", ">", ">=", "<", "<="}

        if self.value_type == "string" and self.operator not in string_operators:
            raise ValueError("字符串类型仅支持 等于/不等于/包含/不包含")
        if self.value_type == "number" and self.operator not in number_operators:
            raise ValueError("数字类型仅支持 等于/不等于/大于/大于等于/小于/小于等于")
        return self


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
