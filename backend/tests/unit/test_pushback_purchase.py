"""Unit tests for app.pushback.purchase.

Tests the push_saihu_job business logic by mocking the database session
factory and the Saihu create_purchase_order endpoint.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import PushBlockedError, SaihuAPIError
from app.pushback.purchase import (
    _join_purchase_order_numbers,
    _refresh_suggestion_counts,
    push_saihu_job,
)


class _FakeContext:
    """Minimal JobContext stub for tests."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.task_id = 1
        self.job_name = "push_saihu"
        self.payload = payload
        self.progress_calls: list[dict[str, Any]] = []

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.progress_calls.append(
            {"current_step": current_step, "step_detail": step_detail, "total_steps": total_steps}
        )


def _make_item(
    item_id: int,
    *,
    commodity_id: str | None = "C001",
    total_qty: int = 10,
    push_blocker: str | None = None,
    push_status: str = "pending",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        commodity_id=commodity_id,
        total_qty=total_qty,
        push_blocker=push_blocker,
        push_status=push_status,
        suggestion_id=100,
    )


def _make_config(warehouse_id: str = "WH-001") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        default_purchase_warehouse_id=warehouse_id,
        include_tax="0",
    )


def _make_suggestion(status: str = "draft") -> SimpleNamespace:
    return SimpleNamespace(id=100, status=status)


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> "_ScalarsProxy":
        return _ScalarsProxy(self._value)


class _ScalarsProxy:
    def __init__(self, values: Any) -> None:
        self._values = values if isinstance(values, list) else [values]

    def all(self) -> list[Any]:
        return list(self._values)


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.commits = 0

    async def execute(self, stmt: Any) -> Any:
        if self._responses:
            return self._responses.pop(0)
        return _ScalarResult(None)

    async def commit(self) -> None:
        self.commits += 1


class _FakeSessionFactory:
    """Async context manager factory that yields preconfigured _FakeDb instances."""

    def __init__(self, db_sequence: list[_FakeDb]) -> None:
        self._dbs = list(db_sequence)

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> _FakeDb:
        return self._dbs.pop(0)

    async def __aexit__(self, *args: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_push_saihu_job_success_path() -> None:
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1, 2]})
    items = [_make_item(1), _make_item(2)]

    # First db context: load config + items
    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult(items),
        ]
    )
    # Second db context: update items + refresh counts
    db2 = _FakeDb(
        [
            None,  # update SuggestionItem
            _ScalarResult(_make_suggestion()),
            _ScalarResult(["pushed", "pushed"]),  # refresh counts select
            None,  # update Suggestion status
        ]
    )
    factory = _FakeSessionFactory([db1, db2])

    mock_api = AsyncMock(return_value=[{"purchaseOrderNo": "PO-XYZ"}])

    with patch("app.pushback.purchase.async_session_factory", factory), \
         patch("app.pushback.purchase.create_purchase_order", mock_api):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_awaited_once()
    call_kwargs = mock_api.call_args.kwargs
    assert call_kwargs["warehouse_id"] == "WH-001"
    assert call_kwargs["items"] == [
        {"commodityId": "C001", "num": "10"},
        {"commodityId": "C001", "num": "10"},
    ]
    assert call_kwargs["include_tax"] == "0"
    assert call_kwargs["action"] == "1"
    assert call_kwargs["custom_purchase_no"] == "RS-100-1"

    assert db1.commits == 0
    assert db2.commits == 2


def test_join_purchase_order_numbers_handles_multiple_rows() -> None:
    assert _join_purchase_order_numbers(
        [
            {"purchaseOrderNo": "PO-001"},
            {"purchaseOrderNo": "PO-002"},
        ]
    ) == "PO-001,PO-002"


def test_join_purchase_order_numbers_dedupes_and_skips_empty_values() -> None:
    assert _join_purchase_order_numbers(
        [
            {"purchaseOrderNo": "PO-001"},
            {"purchaseOrderNo": " PO-001 "},
            {"purchaseOrderNo": ""},
            {},
        ]
    ) == "PO-001"


def test_make_custom_purchase_no_is_stable_and_compact() -> None:
    from app.pushback.purchase import _make_custom_purchase_no

    assert _make_custom_purchase_no(100, 1) == "RS-100-1"


@pytest.mark.asyncio
async def test_push_saihu_job_raises_on_blocker() -> None:
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1]})
    blocked_item = _make_item(1, push_blocker="missing_commodity_id", commodity_id=None)
    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult([blocked_item]),
        ]
    )
    factory = _FakeSessionFactory([db1])

    mock_api = AsyncMock()
    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        pytest.raises(PushBlockedError),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_push_saihu_job_failure_writes_error() -> None:
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1]})
    items = [_make_item(1)]

    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult(items),
        ]
    )
    db2 = _FakeDb(
        [
            None,  # update SuggestionItem (failed branch)
            _ScalarResult(_make_suggestion()),
            _ScalarResult(["push_failed"]),  # refresh counts
            None,  # update Suggestion status
        ]
    )
    factory = _FakeSessionFactory([db1, db2])

    mock_settings = SimpleNamespace(push_auto_retry_times=1)

    api_error = SaihuAPIError("server error", code=50000)
    mock_api = AsyncMock(side_effect=api_error)

    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        patch("app.pushback.purchase.get_settings", return_value=mock_settings),
        pytest.raises(SaihuAPIError),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    assert db2.commits == 2


@pytest.mark.asyncio
async def test_push_saihu_job_does_not_retry_network_error() -> None:
    from app.core.exceptions import SaihuNetworkError

    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1]})
    items = [_make_item(1)]

    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult(items),
        ]
    )
    db2 = _FakeDb(
        [
            None,
            _ScalarResult(_make_suggestion()),
            _ScalarResult(["push_failed"]),
            None,
        ]
    )
    factory = _FakeSessionFactory([db1, db2])

    mock_settings = SimpleNamespace(push_auto_retry_times=3)
    mock_api = AsyncMock(side_effect=SaihuNetworkError("timeout", endpoint="/api/purchase/create.json"))

    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        patch("app.pushback.purchase.get_settings", return_value=mock_settings),
        pytest.raises(SaihuAPIError),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_awaited_once()


@pytest.mark.asyncio
async def test_push_saihu_job_rejects_empty_payload() -> None:
    ctx = _FakeContext({})
    with pytest.raises(ValueError, match="suggestion_id 或 item_ids"):
        await push_saihu_job(ctx)  # type: ignore[arg-type]


# ---- Direct tests for _refresh_suggestion_counts ----


@pytest.mark.asyncio
async def test_refresh_counts_all_pushed() -> None:
    db = _FakeDb(
        [
            _ScalarResult(_make_suggestion()),
            _ScalarResult(["pushed", "pushed", "pushed"]),
            None,
        ]
    )
    await _refresh_suggestion_counts(db, 100)  # type: ignore[arg-type]
    assert len(db._responses) == 0


@pytest.mark.asyncio
async def test_refresh_counts_none_pushed() -> None:
    db = _FakeDb(
        [
            _ScalarResult(_make_suggestion()),
            _ScalarResult(["pending", "pending"]),
            None,
        ]
    )
    await _refresh_suggestion_counts(db, 100)  # type: ignore[arg-type]
    assert len(db._responses) == 0


@pytest.mark.asyncio
async def test_refresh_counts_partial() -> None:
    db = _FakeDb(
        [
            _ScalarResult(_make_suggestion()),
            _ScalarResult(["pushed", "push_failed", "pending"]),
            None,
        ]
    )
    await _refresh_suggestion_counts(db, 100)  # type: ignore[arg-type]
    assert len(db._responses) == 0


@pytest.mark.asyncio
async def test_push_saihu_job_rejects_all_zero_qty() -> None:
    """Reject zero-qty selections before any Saihu request is sent."""
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1, 2]})
    items = [_make_item(1, total_qty=0), _make_item(2, total_qty=0)]

    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult(items),
        ]
    )
    factory = _FakeSessionFactory([db1])

    mock_api = AsyncMock()
    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        pytest.raises(PushBlockedError, match="total_qty<=0"),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_push_saihu_job_rejects_mixed_zero_qty_items() -> None:
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1, 2]})
    items = [_make_item(1, total_qty=10), _make_item(2, total_qty=0)]

    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult(items),
        ]
    )
    factory = _FakeSessionFactory([db1])

    mock_api = AsyncMock()
    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        pytest.raises(PushBlockedError, match="total_qty<=0"),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_push_saihu_job_rejects_already_pushed_items() -> None:
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1, 2]})
    items = [_make_item(1, push_status="pushed"), _make_item(2)]
    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion()),
            _ScalarResult(items),
        ]
    )
    factory = _FakeSessionFactory([db1])

    mock_api = AsyncMock()
    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        pytest.raises(PushBlockedError, match="已推送"),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_push_saihu_job_rejects_archived_suggestion() -> None:
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1]})
    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(_make_suggestion(status="archived")),
        ]
    )
    factory = _FakeSessionFactory([db1])

    mock_api = AsyncMock()
    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        pytest.raises(PushBlockedError, match="已归档"),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_counts_preserves_archived_status() -> None:
    db = _FakeDb(
        [
            _ScalarResult(_make_suggestion(status="archived")),
            _ScalarResult(["pushed", "push_failed"]),
            None,
        ]
    )
    await _refresh_suggestion_counts(db, 100)  # type: ignore[arg-type]
    assert len(db._responses) == 0
