"""配置相关 Pydantic DTO(contracts/config.yaml)。"""

from datetime import datetime
from typing import Literal

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from app.core.restock_regions import normalize_restock_regions


# ==================== Global Config ====================
class GlobalConfigOut(BaseModel):
    buffer_days: int
    target_days: int
    lead_time_days: int
    safety_stock_days: int = Field(default=15, ge=1, le=90)
    restock_regions: list[str] = Field(default_factory=list)
    eu_countries: list[str] = Field(default_factory=list)
    sync_interval_minutes: int
    scheduler_enabled: bool
    shop_sync_mode: Literal["all", "specific"]

    model_config = {"from_attributes": True}

    @field_validator("restock_regions", mode="before")
    @classmethod
    def validate_restock_regions(cls, value: list[str] | None) -> list[str]:
        return normalize_restock_regions(value)


class GlobalConfigPatch(BaseModel):
    buffer_days: int | None = Field(default=None, ge=1, le=365)
    target_days: int | None = Field(default=None, ge=1, le=365)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    safety_stock_days: int | None = Field(default=None, ge=1, le=90)
    restock_regions: list[str] | None = None
    eu_countries: list[str] | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    scheduler_enabled: bool | None = None
    shop_sync_mode: Literal["all", "specific"] | None = None

    @field_validator("restock_regions", mode="before")
    @classmethod
    def validate_restock_regions(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_restock_regions(value)

    @field_validator("eu_countries", mode="before")
    @classmethod
    def validate_eu_countries(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_restock_regions(value)

    @model_validator(mode="after")
    def validate_target_vs_lead_time(self) -> "GlobalConfigPatch":
        if (
            self.target_days is not None
            and self.lead_time_days is not None
            and self.target_days < self.lead_time_days
        ):
            raise ValueError("目标库存天数不能小于采购提前期")
        return self


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
_BETWEEN_MAX_SEGMENTS = 20


def _parse_between_segments(raw: str) -> list[tuple[int, int]]:
    """解析 between compare_value '000-270, 500-700' -> [(0,270),(500,700)]。

    仅做纯语法/数值校验,不做 prefix_length 越界检查(由调用方负责)。
    遇到错误抛 ValueError。
    """
    segments: list[tuple[int, int]] = []
    for chunk in raw.split(","):
        piece = chunk.strip()
        if not piece:
            continue
        parts = piece.split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"between 段 '{piece}' 格式错误,需为 数字-数字")
        lo_raw, hi_raw = parts[0].strip(), parts[1].strip()
        if not lo_raw.isdigit() or not hi_raw.isdigit():
            raise ValueError(f"between 段 '{piece}' 格式错误,需为 数字-数字")
        lo, hi = int(lo_raw), int(hi_raw)
        if lo > hi:
            raise ValueError(f"between 区间下界不能大于上界: {piece}")
        segments.append((lo, hi))
    return segments


class ZipcodeRuleIn(BaseModel):
    country: str = Field(..., min_length=2, max_length=2)
    prefix_length: int = Field(..., ge=1, le=10)
    value_type: Literal["number", "string"]
    operator: Literal[
        "=", "!=", ">", ">=", "<", "<=", "contains", "not_contains", "between"
    ]
    compare_value: str = Field(..., min_length=1, max_length=200)
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
        prefix_length = info.data.get("prefix_length")

        if operator == "between":
            if value_type != "number":
                raise ValueError("between 运算符仅支持 number 值类型")
            try:
                segments = _parse_between_segments(compare_value)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            if not segments:
                raise ValueError("between 至少需要一个有效区间段")
            if len(segments) > _BETWEEN_MAX_SEGMENTS:
                raise ValueError(
                    f"between 段数不能超过 {_BETWEEN_MAX_SEGMENTS},当前 {len(segments)}"
                )
            if prefix_length is not None:
                max_value = 10**prefix_length - 1
                for _, hi in segments:
                    if hi > max_value:
                        raise ValueError(
                            f"between 上界 {hi} 超出前 {prefix_length} 位最大值 {max_value}"
                        )
            return compare_value

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
        number_operators = {"=", "!=", ">", ">=", "<", "<=", "between"}

        if self.value_type == "string" and self.operator not in string_operators:
            raise ValueError("字符串类型仅支持 等于/不等于/包含/不包含")
        if self.value_type == "number" and self.operator not in number_operators:
            raise ValueError("数字类型仅支持 等于/不等于/大于/大于等于/小于/小于等于/区间")
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


# ==================== Generation Toggle ====================
class GenerationToggleOut(BaseModel):
    enabled: bool
    updated_by: int | None = None
    updated_by_name: str | None = None
    updated_at: datetime | None = None
    can_enable: bool = True
    can_enable_reason: str | None = None

    model_config = {"from_attributes": True}


class GenerationTogglePatch(BaseModel):
    enabled: bool
