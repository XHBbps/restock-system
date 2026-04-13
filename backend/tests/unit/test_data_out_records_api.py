from sqlalchemy import select

from app.api.data import _apply_out_record_sort
from app.models.in_transit import InTransitRecord


def test_apply_out_record_sort_defaults_to_update_time_desc() -> None:
    stmt = _apply_out_record_sort(select(InTransitRecord), None, "desc")
    sql = str(stmt)

    assert "update_time DESC" in sql


def test_apply_out_record_sort_supports_warehouse_id_column() -> None:
    stmt = _apply_out_record_sort(select(InTransitRecord), "warehouseId", "asc")
    sql = str(stmt)

    assert "warehouse_id ASC" in sql
