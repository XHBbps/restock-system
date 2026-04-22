from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EngineContext:
    country_qty: dict[str, dict[str, int]] = field(default_factory=dict)
    velocity: dict[str, dict[str, float]] = field(default_factory=dict)
    local_stock: dict[str, dict[str, int]] = field(default_factory=dict)
    buffer_days: int = 30
    safety_stock_days: int = 15
