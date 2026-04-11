import pytest
from pydantic import ValidationError

from app.schemas.config import GlobalConfigPatch, ZipcodeRuleIn


def test_global_config_patch_accepts_valid_cron() -> None:
    patch = GlobalConfigPatch(calc_cron="0 8 * * *")

    assert patch.calc_cron == "0 8 * * *"


def test_global_config_patch_rejects_invalid_cron() -> None:
    with pytest.raises(ValidationError):
        GlobalConfigPatch(calc_cron="invalid cron")


def test_zipcode_rule_accepts_string_contains_operator() -> None:
    rule = ZipcodeRuleIn(
        country="UK",
        prefix_length=4,
        value_type="string",
        operator="contains",
        compare_value="SW, EC",
        warehouse_id="wh-1",
        priority=10,
    )

    assert rule.compare_value == "SW, EC"


def test_zipcode_rule_rejects_invalid_operator_for_string() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(
            country="UK",
            prefix_length=4,
            value_type="string",
            operator=">=",
            compare_value="SW",
            warehouse_id="wh-1",
            priority=10,
        )


def test_zipcode_rule_rejects_invalid_operator_for_number() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(
            country="JP",
            prefix_length=2,
            value_type="number",
            operator="contains",
            compare_value="50",
            warehouse_id="wh-1",
            priority=10,
        )


def test_zipcode_rule_rejects_empty_contains_tokens() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(
            country="UK",
            prefix_length=4,
            value_type="string",
            operator="contains",
            compare_value=" ,  , ",
            warehouse_id="wh-1",
            priority=10,
        )


def test_zipcode_rule_rejects_invalid_number_compare_value() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(
            country="JP",
            prefix_length=2,
            value_type="number",
            operator=">=",
            compare_value="SW,EC",
            warehouse_id="wh-1",
            priority=10,
        )
