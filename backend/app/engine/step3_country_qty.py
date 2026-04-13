"""Step 3:各国建议补货量。

公式(FR-031):
    raw[国] = TARGET_DAYS x velocity[国] - (available + reserved + in_transit)
    country_qty[国] = max(raw, 0)
"""

import math
from collections import defaultdict


def compute_country_qty(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, dict[str, int]]],
    target_days: int,
) -> dict[str, dict[str, int]]:
    """计算各 SKU 各国的补货量。

    返回:
        country_qty[sku][country] = int
    """
    country_qty: defaultdict[str, dict[str, int]] = defaultdict(dict)

    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock_total = inventory.get(sku, {}).get(country, {}).get("total", 0)
            raw = target_days * v - stock_total
            if raw <= 0:
                continue
            # 向上取整到件
            country_qty[sku][country] = math.ceil(raw)
    return dict(country_qty)
