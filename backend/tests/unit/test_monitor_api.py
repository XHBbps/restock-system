import pytest

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
async def test_get_api_calls_returns_endpoint_overview_only() -> None:
    db = _FakeDb([_RowsResult([])])

    result = await get_api_calls(hours=24, db=db, _={})  # type: ignore[arg-type]

    assert result.endpoints == []
    assert len(db.executed) == 1


@pytest.mark.asyncio
async def test_get_api_calls_last_call_sql_has_no_embedded_python_import() -> None:
    """Regression for code review C-1.

    Ensure the "last call per endpoint" text() SQL does not accidentally contain
    a Python import statement inside the string literal. Triggers the `if rows:`
    branch by providing a non-empty first rows result.
    """
    db = _FakeDb([
        _RowsResult([("GET /foo", 10, 8, None)]),  # non-empty -> enters if-branch
        _RowsResult([]),                            # the buggy last_rows query
    ])

    await get_api_calls(hours=24, db=db, _={})  # type: ignore[arg-type]

    # The second executed statement is the text() last_rows SELECT DISTINCT ON.
    last_rows_stmt = db.executed[1]
    sql_text = str(last_rows_stmt).lower()
    assert "from typing import any" not in sql_text, (
        "SQL literal must not contain embedded Python import statement"
    )
    assert "select distinct on" in sql_text
