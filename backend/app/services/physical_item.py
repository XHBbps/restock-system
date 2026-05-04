"""Physical SKU resolution helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.physical_item import PhysicalItemGroup, PhysicalItemSkuAlias


def normalize_sku(value: str) -> str:
    sku = value.strip()
    if not sku:
        raise ValueError("SKU cannot be empty")
    return sku


def normalize_sku_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        sku = normalize_sku(value)
        if sku in seen:
            continue
        seen.add(sku)
        result.append(sku)
    return result


@dataclass(frozen=True, slots=True)
class PhysicalSkuResolver:
    """Resolve inventory SKUs to their enabled shared component group."""

    sku_to_group_key: dict[str, str]
    members_by_group_key: dict[str, list[str]]

    def resolve_inventory_sku(self, sku: str) -> str:
        return self.sku_to_group_key.get(sku, sku)

    def expand_inventory_skus(self, skus: Iterable[str]) -> list[str]:
        result: set[str] = set()
        for sku in skus:
            group_key = self.resolve_inventory_sku(sku)
            members = self.members_by_group_key.get(group_key)
            if members:
                result.update(members)
            else:
                result.add(sku)
        return sorted(result)

    def members_for_group_key(self, group_key: str) -> list[str]:
        return self.members_by_group_key.get(group_key, [group_key])


async def load_physical_sku_resolver(db: AsyncSession) -> PhysicalSkuResolver:
    rows = (
        await db.execute(
            select(
                PhysicalItemSkuAlias.sku,
                PhysicalItemGroup.id,
            )
            .join(PhysicalItemGroup, PhysicalItemGroup.id == PhysicalItemSkuAlias.group_id)
            .where(PhysicalItemGroup.enabled.is_(True))
            .order_by(PhysicalItemGroup.id, PhysicalItemSkuAlias.sku)
        )
    ).all()
    sku_to_group_key: dict[str, str] = {}
    members_by_group_key: defaultdict[str, set[str]] = defaultdict(set)
    for sku, group_id in rows:
        if not isinstance(sku, str) or group_id is None:
            continue
        group_key = f"physical-group:{group_id}"
        sku_to_group_key[sku] = group_key
        members_by_group_key[group_key].add(sku)
    return PhysicalSkuResolver(
        sku_to_group_key=sku_to_group_key,
        members_by_group_key={
            group_key: sorted(members) for group_key, members in members_by_group_key.items()
        },
    )


async def resolve_physical_skus(db: AsyncSession, skus: Iterable[str]) -> dict[str, str]:
    resolver = await load_physical_sku_resolver(db)
    return {sku: resolver.resolve_inventory_sku(sku) for sku in skus}
