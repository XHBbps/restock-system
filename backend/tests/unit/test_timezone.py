from zoneinfo import ZoneInfo

from app.core.countries import BUILTIN_COUNTRY_NAMES, NON_EU_MEMBER_CODES
from app.core.timezone import BEIJING, COUNTRY_TO_TIMEZONE, country_to_tz


def test_country_to_tz_supports_builtin_country_timezones() -> None:
    assert country_to_tz("CZ") == ZoneInfo("Europe/Prague")
    assert country_to_tz("RO") == ZoneInfo("Europe/Bucharest")
    assert country_to_tz("UK") == ZoneInfo("Europe/London")


def test_builtin_countries_have_timezone_mapping() -> None:
    country_codes = set(BUILTIN_COUNTRY_NAMES) - NON_EU_MEMBER_CODES

    assert country_codes <= set(COUNTRY_TO_TIMEZONE)


def test_country_to_tz_unknown_country_falls_back_to_beijing() -> None:
    assert country_to_tz("XX") == BEIJING


def test_country_to_tz_non_real_builtin_country_falls_back_to_beijing() -> None:
    assert country_to_tz("EU") == BEIJING
    assert country_to_tz("ZZ") == BEIJING
