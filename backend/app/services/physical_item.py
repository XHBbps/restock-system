"""Physical SKU resolution helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

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
    """Resolve raw SKUs to their enabled physical-item primary SKU."""

    alias_to_primary: dict[str, str]
    aliases_by_primary: dict[str, list[str]]

    def resolve(self, sku: str) -> str:
        return self.alias_to_primary.get(sku, sku)

    def resolve_many(self, skus: Iterable[str]) -> list[str]:
        return sorted({self.resolve(sku) for sku in skus})

    def source_skus_for(self, skus: Iterable[str]) -> list[str]:
        result: set[str] = set()
        for sku in skus:
            primary = self.resolve(sku)
            aliases = self.aliases_by_primary.get(primary)
            if aliases:
                result.update(aliases)
            else:
                result.add(sku)
        return sorted(result)

    def aliases_for(self, primary_sku: str) -> list[str]:
        return self.aliases_by_primary.get(primary_sku, [primary_sku])


async def load_physical_sku_resolver(db: AsyncSession) -> PhysicalSkuResolver:
    rows = (
        await db.execute(
            select(PhysicalItemSkuAlias.sku, PhysicalItemGroup.primary_sku)
            .join(PhysicalItemGroup, PhysicalItemGroup.id == PhysicalItemSkuAlias.group_id)
            .where(PhysicalItemGroup.enabled.is_(True))
            .order_by(PhysicalItemGroup.primary_sku, PhysicalItemSkuAlias.sku)
        )
    ).all()
    alias_to_primary: dict[str, str] = {}
    aliases_by_primary: defaultdict[str, set[str]] = defaultdict(set)
    for sku, primary_sku in rows:
        if not isinstance(sku, str) or not isinstance(primary_sku, str):
            continue
        alias_to_primary[sku] = primary_sku
        aliases_by_primary[primary_sku].add(sku)
        aliases_by_primary[primary_sku].add(primary_sku)
    return PhysicalSkuResolver(
        alias_to_primary=alias_to_primary,
        aliases_by_primary={
            primary_sku: sorted(aliases) for primary_sku, aliases in aliases_by_primary.items()
        },
    )


async def resolve_physical_skus(db: AsyncSession, skus: Iterable[str]) -> dict[str, str]:
    resolver = await load_physical_sku_resolver(db)
    return {sku: resolver.resolve(sku) for sku in skus}
