import pytest
from pydantic import ValidationError

from app.schemas.config import GlobalConfigPatch, ZipcodeRuleIn


def test_global_config_patch_accepts_valid_cron() -> None:
    patch = GlobalConfigPatch(calc_cron="0 8 * * *")

    assert patch.calc_cron == "0 8 * * *"


def test_global_config_patch_rejects_invalid_cron() -> None:
    with pytest.raises(ValidationError):
        GlobalConfigPatch(calc_cron="invalid cron")


def test_global_config_patch_normalizes_restock_regions() -> None:
    patch = GlobalConfigPatch(restock_regions=["us", " GB ", "", "us"])

    assert patch.restock_regions == ["US", "GB"]


def test_global_config_patch_rejects_invalid_restock_region() -> None:
    with pytest.raises(ValidationError, match="补货区域国家码无效"):
        GlobalConfigPatch(restock_regions=["USA"])


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
    with pytest.raises(ValidationError, match="格式"):
        ZipcodeRuleIn(**_valid_between_body(compare_value="000_270"))


def test_zipcode_rule_in_rejects_between_lo_gt_hi() -> None:
    with pytest.raises(ValidationError, match="下界"):
        ZipcodeRuleIn(**_valid_between_body(compare_value="300-270"))


def test_zipcode_rule_in_rejects_between_hi_exceeds_prefix_length() -> None:
    # prefix_length=3 → 最大值 999
    with pytest.raises(ValidationError, match="超出"):
        ZipcodeRuleIn(**_valid_between_body(compare_value="000-1000"))


def test_zipcode_rule_in_rejects_between_too_many_segments() -> None:
    segments = ",".join(f"{i}00-{i}50" for i in range(21))  # 21 段
    with pytest.raises(ValidationError, match="段数"):
        ZipcodeRuleIn(**_valid_between_body(compare_value=segments))
