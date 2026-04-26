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

from sqlalchemy import case, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_config import GlobalConfig
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
    return {str(code).upper() for code in values if code}


def apply_eu_mapping(country: str | None, eu_countries: set[str]) -> str | None:
    """将国家码映射为 `'EU'`（若在 eu_countries 中），否则原样返回。

    边界：
    - `None` 保持 `None`
    - 空字符串 `''` 保持 `''`
    - 已经是 `'EU'` 的输入始终保持 `'EU'`（幂等）
    - 空集合 → 等价于恒等函数
    """
    if country is None:
        return None
    if country == "EU":
        return "EU"
    if country in eu_countries:
        return "EU"
    return country


async def backfill_order_eu_country_mapping(
    db: AsyncSession,
    eu_countries: Iterable[str],
) -> int:
    """按当前 EU 配置重新归一化本地历史订单国家码。

    源国家优先取 `original_country_code`，缺失时取当前 `country_code`。源国家属于
    `eu_countries` 时写为 `EU` 并保留原国家；否则恢复源国家并清空原国家字段。
    """
    normalized_eu_countries = {str(code).strip().upper() for code in eu_countries if code}
    source_country = func.coalesce(OrderHeader.original_country_code, OrderHeader.country_code)
    is_eu_country = source_country.in_(sorted(normalized_eu_countries))
    mapped_country = case((is_eu_country, "EU"), else_=source_country)
    mapped_original_country = case((is_eu_country, source_country), else_=None)

    result = await db.execute(
        update(OrderHeader)
        .where(
            or_(
                OrderHeader.country_code.is_distinct_from(mapped_country),
                OrderHeader.marketplace_id.is_distinct_from(mapped_country),
                OrderHeader.original_country_code.is_distinct_from(mapped_original_country),
            )
        )
        .values(
            country_code=mapped_country,
            marketplace_id=mapped_country,
            original_country_code=mapped_original_country,
        )
    )
    return int(result.rowcount or 0)
