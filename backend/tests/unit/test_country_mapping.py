"""单测：country_mapping.apply_eu_mapping。

`load_eu_countries` 依赖 AsyncSession 与 DB，放在集成测试里覆盖；这里只覆
盖纯函数 apply_eu_mapping 的所有边界。
"""

from __future__ import annotations

from app.core.countries import (
    country_label,
    normalize_country_list_for_eu_members,
    normalize_observed_country_code,
)
from app.core.country_mapping import apply_eu_mapping


def test_apply_eu_mapping_country_in_eu_set() -> None:
    assert apply_eu_mapping("DE", {"DE", "FR", "IT"}) == "EU"


def test_apply_eu_mapping_country_not_in_eu_set() -> None:
    assert apply_eu_mapping("US", {"DE", "FR"}) == "US"


def test_apply_eu_mapping_gb_not_in_eu() -> None:
    """UK (GB) 不在 eu_countries，应保持原值。"""
    assert apply_eu_mapping("GB", {"DE", "FR", "IT", "ES", "NL"}) == "GB"
    assert apply_eu_mapping("UK", {"DE", "FR", "IT", "ES", "NL"}) == "GB"


def test_apply_eu_mapping_none_input_returns_none() -> None:
    assert apply_eu_mapping(None, {"DE", "FR"}) is None


def test_apply_eu_mapping_empty_eu_set_is_identity() -> None:
    """eu_countries 为空集合时，函数等价于恒等映射。"""
    assert apply_eu_mapping("DE", set()) == "DE"
    assert apply_eu_mapping("US", set()) == "US"


def test_apply_eu_mapping_literal_eu_is_idempotent() -> None:
    """对已经是 'EU' 的输入幂等，即使 'EU' 不在 eu_countries 里也保持为 'EU'。"""
    assert apply_eu_mapping("EU", {"DE", "FR"}) == "EU"


def test_apply_eu_mapping_empty_string_returns_empty() -> None:
    """空字符串不在集合中，按原值返回（不转为 None 也不映射）。"""
    assert apply_eu_mapping("", {"DE", "FR"}) == ""


def test_normalize_observed_country_code_applies_iso_alias() -> None:
    assert normalize_observed_country_code("uk") == "GB"
    assert normalize_observed_country_code(" GB ") == "GB"


def test_normalize_country_list_for_eu_members_applies_alias_and_dedupes() -> None:
    assert normalize_country_list_for_eu_members(["uk", "gb", "ro"]) == ["GB", "RO"]


def test_country_label_uses_code_and_chinese_name() -> None:
    assert country_label("UK") == "GB - 英国"
    assert country_label("GB") == "GB - 英国"
    assert country_label("CZ") == "CZ - 捷克"
    assert country_label("RO") == "RO - 罗马尼亚"
