"""时区工具。

核心规则(spec FR-007/FR-007a):
赛狐返回的所有时间字段按订单所在站点时区解析,统一转换为
Asia/Shanghai 后存储,避免跨站点订单的窗口边界错位。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from dateutil import parser as date_parser

from app.core.countries import NON_EU_MEMBER_CODES, normalize_observed_country_code

_logger = structlog.get_logger(__name__)

BEIJING = ZoneInfo("Asia/Shanghai")

# marketplaceId 长串 -> 二字码(来源:docs/saihu_api/开发指南/站点对应关系.md)
MARKETPLACE_ID_TO_COUNTRY: dict[str, str] = {
    "ATVPDKIKX0DER": "US",
    "A2EUQ1WTGCTBG2": "CA",
    "A1AM78C64UM0Y8": "MX",
    "A1F83G8C2ARO7P": "GB",
    "A1PA6795UKMFR9": "DE",
    "A13V1IB3VIYZZH": "FR",
    "APJ6JRA9NG5V4": "IT",
    "A1RKKUPIHCS9HS": "ES",
    "A21TJRUUN4KGV": "IN",
    "A1VC38T7YXB528": "JP",
    "A39IBJ37TRP1C6": "AU",
    "A2VIGQ35RCS4UG": "AE",
    "A33AVAJ2PDY3EV": "TR",
    "A19VAU5U5O7RUS": "SG",
    "A2Q3Y263D00KWC": "BR",
    "A1805IZSGTT6HS": "NL",
    "A17E79C6D8DWNP": "SA",
    "A2NODRKZP88ZB9": "SE",
    "A1C3SOZRARQ6R3": "PL",
    "AMEN7PMS3EDWL": "BE",
    "A28R8C7NBKEWEA": "IE",
}

# 国家二字码 -> IANA 时区
COUNTRY_TO_TIMEZONE: dict[str, str] = {
    "US": "America/Los_Angeles",  # 亚马逊 US 默认 PST
    "CA": "America/Toronto",
    "MX": "America/Mexico_City",
    "GB": "Europe/London",
    "CZ": "Europe/Prague",
    "DE": "Europe/Berlin",
    "FR": "Europe/Paris",
    "IT": "Europe/Rome",
    "ES": "Europe/Madrid",
    "NL": "Europe/Amsterdam",
    "RO": "Europe/Bucharest",
    "BE": "Europe/Brussels",
    "SE": "Europe/Stockholm",
    "PL": "Europe/Warsaw",
    "IE": "Europe/Dublin",
    "IN": "Asia/Kolkata",
    "JP": "Asia/Tokyo",
    "AU": "Australia/Sydney",
    "AT": "Europe/Vienna",
    "CH": "Europe/Zurich",
    "CY": "Asia/Nicosia",
    "DK": "Europe/Copenhagen",
    "EE": "Europe/Tallinn",
    "FI": "Europe/Helsinki",
    "LT": "Europe/Vilnius",
    "LV": "Europe/Riga",
    "MT": "Europe/Malta",
    "SI": "Europe/Ljubljana",
    "AE": "Asia/Dubai",
    "TR": "Europe/Istanbul",
    "SG": "Asia/Singapore",
    "BR": "America/Sao_Paulo",
    "SA": "Asia/Riyadh",
    "CN": "Asia/Shanghai",  # 国内仓
}


def marketplace_to_country(marketplace_id: str | None) -> str | None:
    """把 marketplaceId 转为二字码。

    订单列表返回长串(A1VC38T7YXB528),订单详情可能直接返回二字码(JP)。
    两种都兼容。
    """
    if not marketplace_id:
        return None
    normalized_country = normalize_observed_country_code(marketplace_id)
    # 订单详情直接返回二字码
    if normalized_country is not None:
        return normalized_country
    return MARKETPLACE_ID_TO_COUNTRY.get(marketplace_id)


def country_to_tz(country: str | None) -> ZoneInfo:
    """国家 -> ZoneInfo,未知国家回退北京。"""
    normalized_country = normalize_observed_country_code(country)
    if not normalized_country:
        return BEIJING
    tz_name = COUNTRY_TO_TIMEZONE.get(normalized_country)
    if not tz_name:
        if normalized_country not in NON_EU_MEMBER_CODES:
            _logger.warning(
                "unknown_country_timezone_fallback",
                country=normalized_country,
                fallback_timezone=str(BEIJING),
            )
        return BEIJING
    return ZoneInfo(tz_name)


def parse_saihu_time(raw: str | None, marketplace_id: str | None = None) -> datetime | None:
    """把赛狐返回的时间字符串解析为带时区的 datetime。

    输入格式:'2026-04-08 10:11:15' 或 '2026-04-08T10:11:15'
    解析逻辑:按站点时区解析 -> 转换为 Asia/Shanghai
    """
    if not raw:
        return None
    try:
        naive = date_parser.parse(raw)
    except (ValueError, TypeError) as exc:
        # 失败快速(宪法原则 III):时间解析失败应作为结构化事件暴露
        _logger.warning(
            "parse_saihu_time_failed",
            raw=raw,
            marketplace_id=marketplace_id,
            error=str(exc),
        )
        return None
    if naive.tzinfo is not None:
        # 已带时区,直接转北京
        return naive.astimezone(BEIJING)
    country = marketplace_to_country(marketplace_id) if marketplace_id else None
    source_tz = country_to_tz(country)
    aware = naive.replace(tzinfo=source_tz)
    return aware.astimezone(BEIJING)


def now_beijing() -> datetime:
    """当前北京时间(带 tz)。"""
    return datetime.now(BEIJING)
