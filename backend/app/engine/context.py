from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InventoryStock:
    """单 SKU × 国家的海外仓库存快照。

    替换原引擎 step2 中的 ``dict[str, int]`` with keys
    ``{"available","reserved","in_transit","total"}`` — 字符串 key 拼错
    曾多次触发静默 bug。frozen + slots 保证不可变 + 内存紧凑。

    total 是 available + reserved + in_transit 的派生属性，不单独存储。
    """

    available: int
    reserved: int
    in_transit: int

    @property
    def total(self) -> int:
        return self.available + self.reserved + self.in_transit


@dataclass
class EngineContext:
    country_qty: dict[str, dict[str, int]] = field(default_factory=dict)
    velocity: dict[str, dict[str, float]] = field(default_factory=dict)
    local_stock: dict[str, dict[str, int]] = field(default_factory=dict)
    buffer_days: int = 30
    safety_stock_days: int = 15
