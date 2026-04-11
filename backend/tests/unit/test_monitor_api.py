import pytest
from sqlalchemy.dialects import postgresql

from app.api.monitor import get_api_calls


class _RowsResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeDb:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.executed = []

    async def execute(self, stmt, *args, **kwargs):
        self.executed.append(stmt)
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_get_api_calls_counts_only_orders_related_to_matched_skus() -> None:
    db = _FakeDb([
        _RowsResult([]),
        _ScalarResult(2),
    ])

    result = await get_api_calls(hours=24, db=db, _={})  # type: ignore[arg-type]

    assert result.endpoints == []
    assert result.postal_compliance_warning == 2

    compliance_stmt = db.executed[-1]
    sql = str(
        compliance_stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "exists (" in sql
    assert "order_item" in sql
    assert "product_listing" in sql
    assert "product_listing.is_matched is true" in sql
