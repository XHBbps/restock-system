"""EU 国家合并映射工具。

同步任务入口（订单/商品/出库/库存）在写入前调用 `apply_eu_mapping` 把属于
`global_config.eu_countries` 的国家码映射为字面 `'EU'`；原值由调用方存到
对应源表的 `original_*` 审计列。

### 使用模式

每个同步 job 启动时调用 `load_eu_countries(db)` 读取一次当前集合，然后
在循环里把集合作为参数传给 `apply_eu_mapping`。**不要** 在循环里反复查库。

```python
eu_countries = await load_eu_countries(db)
for row in batch:
    mapped = apply_eu_mapping(row.country, eu_countries)
    ...
```
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import case, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import (
    COUNTRY_CODE_ALIASES,
    normalize_country_list_for_eu_members,
    normalize_observed_country_code,
)
from app.models.global_config import GlobalConfig
from app.models.in_transit import InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderHeader


async def load_eu_countries(db: AsyncSession) -> set[str]:
    """读取 `global_config.eu_countries`，返回归一化的大写国家码集合。

    单行表 `global_config.id=1`。若表为空或字段为 null，返回空集合（此时
    `apply_eu_mapping` 退化为恒等函数，不会误映射）。
    """
    config = await db.get(GlobalConfig, 1)
    if config is None:
        return set()
    values = config.eu_countries or []
    return set(normalize_country_list_for_eu_members(values))


def apply_eu_mapping(country: str | None, eu_countries: set[str]) -> str | None:
    """将国家码映射为 `'EU'`（若在 eu_countries 中），否则原样返回。

    边界：
    - `None` 保持 `None`
    - 空字符串 `''` 保持 `''`
    - 已经是 `'EU'` 的输入始终保持 `'EU'`（幂等）
    - 合法 2 位字母国家码会先按别名表标准化，例如 `UK -> GB`
    - 空集合 → 等价于恒等函数
    """
    if country is None:
        return None
    if country == "EU":
        return "EU"
    normalized_country = normalize_observed_country_code(country) or country
    if normalized_country in eu_countries:
        return "EU"
    return normalized_country


def _normalized_country_expr(source_country: Any) -> Any:
    trimmed_upper = func.upper(func.trim(source_country))
    return case(
        *[
            (trimmed_upper == alias, canonical)
            for alias, canonical in sorted(COUNTRY_CODE_ALIASES.items())
        ],
        else_=trimmed_upper,
    )


async def _backfill_eu_mapping_for_columns(
    db: AsyncSession,
    *,
    model: type[Any],
    country_column: Any,
    original_country_column: Any,
    eu_countries: Iterable[str],
    extra_country_columns: tuple[Any, ...] = (),
) -> int:
    normalized_eu_countries = set(normalize_country_list_for_eu_members(eu_countries))
    source_country = func.coalesce(original_country_column, country_column)
    normalized_source_country = _normalized_country_expr(source_country)
    is_eu_country = normalized_source_country.in_(sorted(normalized_eu_countries))
    mapped_country = case((is_eu_country, "EU"), else_=normalized_source_country)
    mapped_original_country = case((is_eu_country, normalized_source_country), else_=None)

    where_clauses = [
        country_column.is_distinct_from(mapped_country),
        original_country_column.is_distinct_from(mapped_original_country),
    ]
    values = {
        country_column.key: mapped_country,
        original_country_column.key: mapped_original_country,
    }
    for extra_column in extra_country_columns:
        where_clauses.append(extra_column.is_distinct_from(mapped_country))
        values[extra_column.key] = mapped_country

    result = await db.execute(
        update(model)
        .where(source_country.is_not(None))
        .where(source_country != "")
        .where(or_(*where_clauses))
        .values(**values)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def backfill_order_eu_country_mapping(
    db: AsyncSession,
    eu_countries: Iterable[str],
) -> int:
    """按当前 EU 配置重新归一化本地历史订单国家码。

    源国家优先取 `original_country_code`，缺失时取当前 `country_code`。源国家属于
    `eu_countries` 时写为 `EU` 并保留原国家；否则恢复源国家并清空原国家字段。
    """
    return await _backfill_eu_mapping_for_columns(
        db,
        model=OrderHeader,
        country_column=OrderHeader.country_code,
        original_country_column=OrderHeader.original_country_code,
        extra_country_columns=(OrderHeader.marketplace_id,),
        eu_countries=eu_countries,
    )


async def backfill_inventory_eu_country_mapping(
    db: AsyncSession,
    eu_countries: Iterable[str],
) -> int:
    return await _backfill_eu_mapping_for_columns(
        db,
        model=InventorySnapshotLatest,
        country_column=InventorySnapshotLatest.country,
        original_country_column=InventorySnapshotLatest.original_country,
        eu_countries=eu_countries,
    )


async def backfill_in_transit_eu_country_mapping(
    db: AsyncSession,
    eu_countries: Iterable[str],
) -> int:
    return await _backfill_eu_mapping_for_columns(
        db,
        model=InTransitRecord,
        country_column=InTransitRecord.target_country,
        original_country_column=InTransitRecord.original_target_country,
        eu_countries=eu_countries,
    )


async def backfill_eu_country_mapping(
    db: AsyncSession,
    eu_countries: Iterable[str],
) -> dict[str, int]:
    return {
        "orders": await backfill_order_eu_country_mapping(db, eu_countries),
        "inventory": await backfill_inventory_eu_country_mapping(db, eu_countries),
        "in_transit": await backfill_in_transit_eu_country_mapping(db, eu_countries),
    }
