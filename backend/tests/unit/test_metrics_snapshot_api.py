from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.metrics import get_dashboard_overview, refresh_dashboard_snapshot


class _ScalarOneOrNoneResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDb:
    def __init__(self, responses) -> None:
        self._responses = list(responses)

    async def execute(self, stmt, *args, **kwargs):
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_dashboard_returns_cached_snapshot_payload_without_recomputing(monkeypatch) -> None:
    import app.api.metrics as metrics_module

    payload = {
        "enabled_sku_count": 12,
        "restock_sku_count": 7,
        "no_restock_sku_count": 5,
        "suggestion_item_count": 8,
        "pushed_count": 3,
        "urgent_count": 5,
        "warning_count": 2,
        "safe_count": 4,
        "risk_country_count": 3,
        "suggestion_id": 10,
        "suggestion_status": "draft",
        "lead_time_days": 20,
        "target_days": 60,
        "country_risk_distribution": [],
        "country_restock_distribution": [],
        "top_urgent_skus": [],
    }
    db = _FakeDb(
        [
            _ScalarOneOrNoneResult(None),
            _ScalarOneOrNoneResult(
                SimpleNamespace(
                    id=1,
                    payload=payload,
                    refreshed_at=datetime(2026, 4, 14, 10, 0, 0),
                    updated_at=datetime(2026, 4, 14, 10, 0, 0),
                )
            ),
        ]
    )

    monkeypatch.setattr(metrics_module, "enqueue_task", pytest.fail)

    result = await get_dashboard_overview(db=db, _={})  # type: ignore[arg-type]

    assert result.snapshot_status == "ready"
    assert result.snapshot_task_id is None
    assert result.restock_sku_count == 7
    assert result.no_restock_sku_count == 5
    assert result.urgent_count == 5
    assert result.warning_count == 2
    assert result.suggestion_id == 10


@pytest.mark.asyncio
async def test_dashboard_marks_cached_snapshot_as_refreshing_when_task_exists(monkeypatch) -> None:
    import app.api.metrics as metrics_module

    payload = {
        "enabled_sku_count": 6,
        "restock_sku_count": 1,
        "no_restock_sku_count": 5,
        "suggestion_item_count": 0,
        "pushed_count": 0,
        "urgent_count": 1,
        "warning_count": 2,
        "safe_count": 3,
        "risk_country_count": 2,
        "suggestion_id": None,
        "suggestion_status": None,
        "lead_time_days": 20,
        "target_days": 60,
        "country_risk_distribution": [],
        "country_restock_distribution": [],
        "top_urgent_skus": [],
    }
    db = _FakeDb(
        [
            _ScalarOneOrNoneResult(SimpleNamespace(id=77)),
            _ScalarOneOrNoneResult(
                SimpleNamespace(
                    id=1,
                    payload=payload,
                    refreshed_at=datetime(2026, 4, 14, 11, 0, 0),
                    updated_at=datetime(2026, 4, 14, 11, 0, 0),
                )
            ),
        ]
    )

    monkeypatch.setattr(metrics_module, "enqueue_task", pytest.fail)

    result = await get_dashboard_overview(db=db, _={})  # type: ignore[arg-type]

    assert result.snapshot_status == "refreshing"
    assert result.snapshot_task_id == 77
    assert result.restock_sku_count == 1
    assert result.safe_count == 3


@pytest.mark.asyncio
async def test_dashboard_enqueues_refresh_when_snapshot_missing(monkeypatch) -> None:
    import app.api.metrics as metrics_module

    db = _FakeDb(
        [
            _ScalarOneOrNoneResult(None),
            _ScalarOneOrNoneResult(None),
        ]
    )

    async def _fake_enqueue_task(*_args, **_kwargs):
        return 88, False

    monkeypatch.setattr(metrics_module, "enqueue_task", _fake_enqueue_task)

    result = await get_dashboard_overview(db=db, _={})  # type: ignore[arg-type]

    assert result.snapshot_status == "refreshing"
    assert result.snapshot_task_id == 88
    assert result.restock_sku_count == 0
    assert result.no_restock_sku_count == 0
    assert result.urgent_count == 0
    assert result.country_risk_distribution == []


@pytest.mark.asyncio
async def test_dashboard_recomputes_when_snapshot_uses_old_card_schema(monkeypatch) -> None:
    import app.api.metrics as metrics_module

    db = _FakeDb(
        [
            _ScalarOneOrNoneResult(None),
            _ScalarOneOrNoneResult(
                SimpleNamespace(
                    id=1,
                    payload={
                        "enabled_sku_count": 6,
                        "suggestion_item_count": 0,
                        "pushed_count": 0,
                        "urgent_count": 1,
                        "warning_count": 2,
                        "safe_count": 3,
                        "risk_country_count": 2,
                        "suggestion_id": None,
                        "suggestion_status": None,
                        "lead_time_days": 20,
                        "target_days": 60,
                        "country_risk_distribution": [],
                        "country_restock_distribution": [],
                        "top_urgent_skus": [],
                    },
                    refreshed_at=datetime(2026, 4, 14, 11, 0, 0),
                    updated_at=datetime(2026, 4, 14, 11, 0, 0),
                )
            ),
        ]
    )

    async def _fake_enqueue_task(*_args, **_kwargs):
        return 66, False

    async def _fake_build_dashboard_payload(*_args, **_kwargs):
        return metrics_module.DashboardOverviewPayload(
            enabled_sku_count=6,
            restock_sku_count=2,
            no_restock_sku_count=4,
            suggestion_item_count=0,
            pushed_count=0,
            urgent_count=1,
            warning_count=2,
            safe_count=3,
            risk_country_count=2,
            suggestion_id=None,
            suggestion_status=None,
            lead_time_days=20,
            target_days=60,
            country_risk_distribution=[],
            country_restock_distribution=[],
            top_urgent_skus=[],
        )

    monkeypatch.setattr(metrics_module, "enqueue_task", _fake_enqueue_task)
    monkeypatch.setattr(metrics_module, "build_dashboard_payload", _fake_build_dashboard_payload)

    result = await get_dashboard_overview(db=db, _={})  # type: ignore[arg-type]

    assert result.snapshot_status == "refreshing"
    assert result.snapshot_task_id == 66
    assert result.restock_sku_count == 2
    assert result.no_restock_sku_count == 4


@pytest.mark.asyncio
async def test_refresh_dashboard_snapshot_enqueues_manual_task(monkeypatch) -> None:
    async def _fake_enqueue_task(*_args, **_kwargs):
        return 99, True

    monkeypatch.setattr("app.api.metrics.enqueue_task", _fake_enqueue_task)

    result = await refresh_dashboard_snapshot(db=_FakeDb([]), _={})  # type: ignore[arg-type]

    assert result.task_id == 99
    assert result.existing is True
