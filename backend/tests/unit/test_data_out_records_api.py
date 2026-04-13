import inspect

from sqlalchemy import select

from app.api.data import _apply_out_record_sort, list_out_records
from app.core.query import escape_like
from app.models.in_transit import InTransitRecord


def test_apply_out_record_sort_defaults_to_update_time_desc() -> None:
    stmt = _apply_out_record_sort(select(InTransitRecord), None, "desc")
    sql = str(stmt)

    assert "update_time DESC" in sql


def test_apply_out_record_sort_supports_warehouse_id_column() -> None:
    stmt = _apply_out_record_sort(select(InTransitRecord), "warehouseId", "asc")
    sql = str(stmt)

    assert "warehouse_id ASC" in sql


def test_out_record_number_filter_uses_ilike() -> None:
    keyword = "OB2603260001"
    stmt = select(InTransitRecord).where(
        InTransitRecord.out_warehouse_no.ilike(f"%{escape_like(keyword)}%", escape="\\")
    )
    compiled = stmt.compile()
    sql = str(compiled)

    assert "out_warehouse_no" in sql
    assert "LIKE" in sql
    assert compiled.params["out_warehouse_no_1"] == f"%{keyword}%"


def test_out_record_number_filter_escapes_like_characters() -> None:
    keyword = "OB%2603_"
    stmt = select(InTransitRecord).where(
        InTransitRecord.out_warehouse_no.ilike(f"%{escape_like(keyword)}%", escape="\\")
    )
    compiled = stmt.compile()

    assert compiled.params["out_warehouse_no_1"] == r"%OB\%2603\_%"


def test_list_out_records_does_not_default_to_in_transit_only() -> None:
    sig = inspect.signature(list_out_records)
    default = sig.parameters["is_in_transit"].default

    assert default.default is None
