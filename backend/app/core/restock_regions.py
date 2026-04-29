"""Helpers for restock region normalization and engine filtering."""

from collections.abc import Iterable

from app.core.countries import normalize_observed_country_code


def normalize_restock_regions(value: Iterable[str] | None) -> list[str]:
    if value is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        raw_code = str(item or "").strip().upper()
        if not raw_code:
            continue
        code = normalize_observed_country_code(raw_code)
        if code is None:
            raise ValueError(f"补货区域国家码无效: {item}")
        if code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def resolve_allowed_restock_regions(value: Iterable[str] | None) -> set[str] | None:
    normalized = normalize_restock_regions(value)
    if not normalized:
        return None
    return set(normalized)
