import pytest
from pydantic import ValidationError

from app.schemas.config import GlobalConfigPatch, ZipcodeRuleIn


def test_global_config_patch_accepts_valid_safety_stock_days() -> None:
    patch = GlobalConfigPatch(safety_stock_days=30)

    assert patch.safety_stock_days == 30


def test_global_config_patch_rejects_invalid_safety_stock_days() -> None:
    with pytest.raises(ValidationError):
        GlobalConfigPatch(safety_stock_days=0)


def test_global_config_patch_normalizes_restock_regions() -> None:
    patch = GlobalConfigPatch(restock_regions=["us", " GB ", "", "us"])

    assert patch.restock_regions == ["US", "GB"]


def test_global_config_patch_normalizes_eu_countries() -> None:
    patch = GlobalConfigPatch(eu_countries=["de", " FR ", "", "de"])

    assert patch.eu_countries == ["DE", "FR"]


def test_global_config_patch_rejects_invalid_restock_region() -> None:
    with pytest.raises(ValidationError):
        GlobalConfigPatch(restock_regions=["USA"])


def test_global_config_patch_rejects_target_days_less_than_lead_time() -> None:
    with pytest.raises(ValidationError):
        GlobalConfigPatch(target_days=20, lead_time_days=30)


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


def _valid_between_body(**overrides):
    base = {
        "country": "JP",
        "prefix_length": 3,
        "value_type": "number",
        "operator": "between",
        "compare_value": "000-270",
        "warehouse_id": "wh-jp",
        "priority": 10,
    }
    base.update(overrides)
    return base


def test_zipcode_rule_in_accepts_single_between_segment() -> None:
    rule = ZipcodeRuleIn(**_valid_between_body())
    assert rule.operator == "between"
    assert rule.compare_value == "000-270"


def test_zipcode_rule_in_accepts_multi_between_segments() -> None:
    rule = ZipcodeRuleIn(**_valid_between_body(compare_value="000-270, 500-700"))
    assert rule.compare_value == "000-270, 500-700"


def test_zipcode_rule_in_rejects_between_with_string_value_type() -> None:
    with pytest.raises(ValidationError, match="between"):
        ZipcodeRuleIn(**_valid_between_body(value_type="string", compare_value="000-270"))


def test_zipcode_rule_in_rejects_between_bad_format() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(**_valid_between_body(compare_value="000_270"))


def test_zipcode_rule_in_rejects_between_lo_gt_hi() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(**_valid_between_body(compare_value="300-270"))


def test_zipcode_rule_in_rejects_between_hi_exceeds_prefix_length() -> None:
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(**_valid_between_body(compare_value="000-1000"))


def test_zipcode_rule_in_rejects_between_too_many_segments() -> None:
    segments = ",".join(f"{i}00-{i}50" for i in range(21))
    with pytest.raises(ValidationError):
        ZipcodeRuleIn(**_valid_between_body(compare_value=segments))
