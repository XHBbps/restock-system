from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.countries import BUILTIN_COUNTRY_NAMES, NON_EU_MEMBER_CODES
from app.core.timezone import BEIJING, COUNTRY_TO_TIMEZONE, country_to_tz, to_order_display_time


def test_country_to_tz_supports_builtin_country_timezones() -> None:
    assert country_to_tz("CZ") == ZoneInfo("Europe/Prague")
    assert country_to_tz("RO") == ZoneInfo("Europe/Bucharest")
    assert country_to_tz("AT") == ZoneInfo("Europe/Vienna")
    assert country_to_tz("CH") == ZoneInfo("Europe/Zurich")
    assert country_to_tz("CY") == ZoneInfo("Asia/Nicosia")
    assert country_to_tz("UK") == ZoneInfo("Europe/London")


def test_builtin_countries_have_timezone_mapping() -> None:
    country_codes = set(BUILTIN_COUNTRY_NAMES) - NON_EU_MEMBER_CODES

    assert country_codes <= set(COUNTRY_TO_TIMEZONE)


def test_country_to_tz_unknown_country_falls_back_to_beijing() -> None:
    assert country_to_tz("XX") == BEIJING


def test_country_to_tz_non_real_builtin_country_falls_back_to_beijing() -> None:
    assert country_to_tz("EU") == BEIJING
    assert country_to_tz("ZZ") == BEIJING


def test_to_order_display_time_prefers_marketplace_timezone() -> None:
    purchase_date = datetime(2026, 5, 12, 1, 30, tzinfo=BEIJING)

    result = to_order_display_time(purchase_date, "ATVPDKIKX0DER", "US")

    assert result == datetime(2026, 5, 11, 10, 30, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert result.isoformat() == "2026-05-11T10:30:00-07:00"


def test_to_order_display_time_uses_country_fallback() -> None:
    purchase_date = datetime(2026, 5, 12, 1, 30, tzinfo=BEIJING)

    result = to_order_display_time(purchase_date, None, "JP")

    assert result == datetime(2026, 5, 12, 2, 30, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_to_order_display_time_unknown_country_falls_back_to_beijing() -> None:
    purchase_date = datetime(2026, 5, 12, 1, 30, tzinfo=BEIJING)

    result = to_order_display_time(purchase_date, None, "ZZ")

    assert result == purchase_date
