import pytest

from app.api.config import _normalize_import_rows
from app.core.exceptions import ValidationFailed


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
    assert [component.inventory_sku for component in rule.components] == ["B", "C"]
    assert [component.quantity for component in rule.components] == [1, 2]


def test_sku_mapping_import_rejects_duplicate_inventory_sku() -> None:
    with pytest.raises(ValidationFailed) as exc:
        _normalize_import_rows(
            [
                {"商品SKU": "A", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
                {"商品SKU": "C", "库存SKU": "B", "组件数量": "1", "启用": "是", "备注": ""},
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
