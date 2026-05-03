import pytest

from app.api.config import _mapping_formula, _normalize_import_rows
from app.core.exceptions import ValidationFailed
from app.models.sku_mapping import SkuMappingComponent, SkuMappingRule


def test_sku_mapping_import_groups_components_by_commodity_sku() -> None:
    rules = _normalize_import_rows(
        [
            {"商品SKU": "A", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": "套装"},
            {"商品SKU": "A", "库存SKU": "C", "组件数量": "2", "启用": "是", "备注": "套装"},
        ]
    )

    rule = rules["A"]
    assert rule.enabled is True
    assert rule.remark == "套装"
    assert [component.group_no for component in rule.components] == [1, 1]
    assert [component.inventory_sku for component in rule.components] == ["B", "C"]
    assert [component.quantity for component in rule.components] == [1, 2]


def test_sku_mapping_formula_separates_alternative_groups() -> None:
    rule = SkuMappingRule(commodity_sku="A", enabled=True)
    rule.components = [
        SkuMappingComponent(group_no=1, inventory_sku="B", quantity=1),
        SkuMappingComponent(group_no=1, inventory_sku="C", quantity=2),
        SkuMappingComponent(group_no=2, inventory_sku="D", quantity=1),
    ]

    assert _mapping_formula(rule) == "A=1*B+2*C 或 1*D"


def test_sku_mapping_component_unique_constraint_is_rule_scoped() -> None:
    unique_names = {
        getattr(constraint, "name", "")
        for constraint in SkuMappingComponent.__table_args__
        if getattr(constraint, "name", "").startswith("uq_")
    }

    assert "uq_sku_mapping_component_rule_inventory" in unique_names
    assert "uq_sku_mapping_component_inventory_sku" not in unique_names


def test_sku_mapping_import_accepts_group_no_column() -> None:
    rules = _normalize_import_rows(
        [
            {
                "商品SKU": "A",
                "组合编号": "1",
                "库存SKU": "B",
                "组件数量": "1",
                "启用": "是",
                "备注": "",
            },
            {
                "商品SKU": "A",
                "组合编号": "2",
                "库存SKU": "C",
                "组件数量": "2",
                "启用": "是",
                "备注": "",
            },
        ]
    )

    rule = rules["A"]
    assert [component.group_no for component in rule.components] == [1, 2]


def test_sku_mapping_import_rejects_invalid_group_no() -> None:
    with pytest.raises(ValidationFailed) as exc:
        _normalize_import_rows(
            [
                {
                    "商品SKU": "A",
                    "组合编号": "0",
                    "库存SKU": "B",
                    "组件数量": "1",
                    "启用": "是",
                    "备注": "",
                }
            ]
        )

    assert exc.value.detail["errors"][0]["message"] == "组合编号必须为正整数"


def test_sku_mapping_import_allows_shared_inventory_sku_across_commodity_skus() -> None:
    rules = _normalize_import_rows(
        [
            {"商品SKU": "A", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
            {"商品SKU": "C", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
        ]
    )

    assert set(rules) == {"A", "C"}
    assert rules["A"].components[0].inventory_sku == "B"
    assert rules["C"].components[0].inventory_sku == "B"


def test_sku_mapping_import_rejects_duplicate_inventory_sku_in_same_rule() -> None:
    with pytest.raises(ValidationFailed) as exc:
        _normalize_import_rows(
            [
                {"商品SKU": "A", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
                {"商品SKU": "A", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
            ]
        )

    assert exc.value.message == "导入校验失败"
    assert "库存SKU与第 2 行重复" in exc.value.detail["errors"][0]["message"]


def test_sku_mapping_import_rejects_invalid_quantity() -> None:
    with pytest.raises(ValidationFailed) as exc:
        _normalize_import_rows(
            [{"商品SKU": "A", "库存SKU": "B", "组件数量": "0", "启用": "是", "备注": ""}]
        )

    assert exc.value.detail["errors"][0]["message"] == "组件数量必须为正整数"


def test_sku_mapping_import_rejects_mixed_rule_enabled_state() -> None:
    with pytest.raises(ValidationFailed) as exc:
        _normalize_import_rows(
            [
                {"商品SKU": "A", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
                {"商品SKU": "A", "库存SKU": "C", "组件数量": "1", "启用": "否", "备注": ""},
            ]
        )

    assert "启用状态不一致" in exc.value.detail["errors"][0]["message"]
