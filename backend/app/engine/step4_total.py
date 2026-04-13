"""Step 4:总采购量。

公式(FR-032):
    total = Σ country_qty[国]                       仅累加 country_qty > 0 的国家
          + Σ velocity[国] x BUFFER_DAYS            同样仅累加 country_qty > 0 的国家
          - (本地仓 available + 本地仓 reserved)

    total = max(total, 0)

本地仓识别:warehouse.type = 1
"""

import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.inventory import InventorySnapshotLatest
from app.models.warehouse import Warehouse

logger = get_logger(__name__)


async def load_local_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[str, dict[str, int]]:
    """加载本地仓(type=1)库存,按 SKU 聚合。"""
    stmt = (
        select(
            InventorySnapshotLatest.commodity_sku,
            func.sum(InventorySnapshotLatest.available).label("avail"),
            func.sum(InventorySnapshotLatest.reserved).label("reserv"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(Warehouse.type == 1)
        .group_by(InventorySnapshotLatest.commodity_sku)
    )
    if commodity_skus is not None:
        stmt = stmt.where(InventorySnapshotLatest.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).all()
    return {sku: {"available": int(a or 0), "reserved": int(r or 0)} for sku, a, r in rows}


def compute_total(
    sku: str,
    country_qty_for_sku: dict[str, int],
    velocity_for_sku: dict[str, float],
    local_stock_for_sku: dict[str, int] | None,
    buffer_days: int,
) -> int:
    """计算单个 SKU 的总采购量。

    仅累加 `country_qty > 0` 的国家(spec 显式要求)。
    同时显式保持 total_qty >= sum(country_breakdown),避免人工编辑后出现
    "分国家数量之和大于总采购量" 的自相矛盾状态。
    """
    if not country_qty_for_sku:
        return 0
    sum_qty = 0
    sum_velocity = 0.0
    for country, qty in country_qty_for_sku.items():
        if qty <= 0:
            continue
        sum_qty += qty
        sum_velocity += velocity_for_sku.get(country, 0.0)

    buffer_qty = sum_velocity * buffer_days
    local_total = 0
    if local_stock_for_sku:
        local_total = local_stock_for_sku.get("available", 0) + local_stock_for_sku.get(
            "reserved", 0
        )

    raw = sum_qty + buffer_qty - local_total
    # 业务规则: 国内库存(type=1)仅用于抵消 buffer 部分,不影响各国实际补货需求。
    # Invariant: total_qty >= sum(country_breakdown),保证人工编辑后
    # "分国家数量之和不超过总采购量" 的约束始终成立(H4 PATCH 校验依赖)。
    if raw < sum_qty:
        logger.info(
            "step4_invariant_adjusted",
            sku=sku,
            original_raw=raw,
            adjusted_to=sum_qty,
            buffer_qty=buffer_qty,
            local_total=local_total,
        )
        raw = sum_qty
    return max(math.ceil(raw), 0)
