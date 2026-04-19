"""权限码注册表覆盖测试。"""

from app.core.permissions import ALL_CODES, REGISTRY


def test_restock_export_registered():
    assert "restock:export" in ALL_CODES
    codes = [p.code for p in REGISTRY]
    assert "restock:export" in codes


def test_restock_new_cycle_registered():
    assert "restock:new_cycle" in ALL_CODES
    codes = [p.code for p in REGISTRY]
    assert "restock:new_cycle" in codes


def test_new_perms_grouped_under_restock():
    by_code = {p.code: p for p in REGISTRY}
    assert by_code["restock:export"].group_name == "补货发起"
    assert by_code["restock:new_cycle"].group_name == "补货发起"
