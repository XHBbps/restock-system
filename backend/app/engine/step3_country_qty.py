"""Step 3:各国建议补货量。

公式(FR-031):
    raw[国] = effective_target_days x velocity[国] - (available + reserved + in_transit)
    country_qty[国] = max(raw, 0)
"""

import math
from collections import defaultdict

from app.engine.context import CountryQtyMap, InventoryMap, VelocityMap


def compute_country_qty(
    velocity: VelocityMap,
    inventory: InventoryMap,
    target_days: int,
) -> CountryQtyMap:
    """计算各 SKU 各国的补货量。

    返回:
        country_qty[sku][country] = int
    """
    country_qty: defaultdict[str, dict[str, int]] = defaultdict(dict)

    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock = inventory.get(sku, {}).get(country)
            stock_total = stock.total if stock is not None else 0
            raw = target_days * v - stock_total
            if raw <= 0:
                continue
            # 向上取整到件
            country_qty[sku][country] = math.ceil(raw)
    return dict(country_qty)
