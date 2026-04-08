"""Step 3：各国建议补货量。

公式（FR-031）：
    raw[国] = TARGET_DAYS × velocity[国] − (available + reserved + in_transit)
    country_qty[国] = max(raw, 0)
    raw < 0 的国家记入 overstock_countries（只读提示）
"""

from collections import defaultdict


def compute_country_qty(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, dict[str, int]]],
    target_days: int,
) -> tuple[dict[str, dict[str, int]], dict[str, list[str]]]:
    """计算各 SKU 各国的补货量。

    返回：
        country_qty[sku][country] = int
        overstock_countries[sku] = [country, ...]
    """
    country_qty: defaultdict[str, dict[str, int]] = defaultdict(dict)
    overstock: defaultdict[str, list[str]] = defaultdict(list)

    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock_total = inventory.get(sku, {}).get(country, {}).get("total", 0)
            raw = target_days * v - stock_total
            if raw <= 0:
                # 库存超目标 → 积压国家（只记录 raw < 0 的）
                if raw < 0:
                    overstock[sku].append(country)
                continue
            # 向上取整到件
            country_qty[sku][country] = int(round(raw))
    return dict(country_qty), dict(overstock)
