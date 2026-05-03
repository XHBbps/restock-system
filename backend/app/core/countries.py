"""Country code helpers shared by config APIs and sync jobs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

BUILTIN_COUNTRY_NAMES: dict[str, str] = {
    "EU": "欧盟",
    "ZZ": "无法识别国家",
    "CN": "中国",
    "US": "美国",
    "CA": "加拿大",
    "MX": "墨西哥",
    "GB": "英国",
    "CZ": "捷克",
    "DE": "德国",
    "FR": "法国",
    "IT": "意大利",
    "ES": "西班牙",
    "IN": "印度",
    "JP": "日本",
    "AU": "澳大利亚",
    "AT": "奥地利",
    "CH": "瑞士",
    "CY": "塞浦路斯",
    "DK": "丹麦",
    "EE": "爱沙尼亚",
    "FI": "芬兰",
    "LT": "立陶宛",
    "LV": "拉脱维亚",
    "MT": "马耳他",
    "SI": "斯洛文尼亚",
    "AE": "阿联酋",
    "TR": "土耳其",
    "SG": "新加坡",
    "BR": "巴西",
    "NL": "荷兰",
    "RO": "罗马尼亚",
    "SA": "沙特阿拉伯",
    "SE": "瑞典",
    "PL": "波兰",
    "BE": "比利时",
    "IE": "爱尔兰",
}

BUILTIN_COUNTRY_ORDER = tuple(BUILTIN_COUNTRY_NAMES.keys())
NON_EU_MEMBER_CODES = {"EU", "ZZ"}
COUNTRY_CODE_ALIASES: dict[str, str] = {
    "UK": "GB",
}


def country_label(code: str) -> str:
    raw_code = code.strip().upper()
    normalized = COUNTRY_CODE_ALIASES.get(raw_code, raw_code)
    name = BUILTIN_COUNTRY_NAMES.get(normalized)
    if name is None:
        return normalized
    return f"{normalized} - {name}"


def is_valid_observed_country_code(value: Any) -> bool:
    code = str(value or "").strip().upper()
    return len(code) == 2 and code.isalpha()


def normalize_observed_country_code(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    if not is_valid_observed_country_code(code):
        return None
    return COUNTRY_CODE_ALIASES.get(code, code)


def normalize_source_country_or_unknown(
    value: Any,
    *,
    event: str,
    **log_context: Any,
) -> str:
    code = normalize_observed_country_code(value)
    if code is not None:
        return code
    logger.warning(event, raw_country=value, fallback_country="ZZ", **log_context)
    return "ZZ"


def normalize_country_list_for_eu_members(value: Iterable[str] | None) -> list[str]:
    if value is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        raw_code = str(item or "").strip().upper()
        if not raw_code:
            continue
        if len(raw_code) != 2 or not raw_code.isalpha():
            raise ValueError(f"EU 成员国国家码无效: {item}")
        code = COUNTRY_CODE_ALIASES.get(raw_code, raw_code)
        if code in NON_EU_MEMBER_CODES:
            raise ValueError(f"{code} 不能加入 EU 成员国")
        if code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized
