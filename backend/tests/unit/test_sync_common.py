from datetime import datetime
from typing import Any


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []
        self.commits = 0

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)

    async def commit(self) -> None:
        self.commits += 1


def _compiled_params(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


async def test_mark_sync_success_uses_explicit_success_watermark() -> None:
    from app.sync.common import mark_sync_success

    db = _FakeDb()
    started = datetime(2026, 4, 29, 10, 0, 0)
    success_at = datetime(2026, 4, 29, 10, 5, 0)

    await mark_sync_success(
        db,  # type: ignore[arg-type]
        "sync_order_list",
        started,
        success_at=success_at,
    )

    params = _compiled_params(db.statements[0])
    assert params["last_run_at"] == started
    assert params["last_success_at"] == success_at
    assert db.commits == 1
