from datetime import date, timedelta
from types import SimpleNamespace

import pytest

import app.api.metrics as metrics_module
from app.api.metrics import build_dashboard_payload


class _ScalarOneResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one(self):
        return self._value


class _ScalarOneOrNoneResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsResult:
    def __init__(self, values) -> None:
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _RowsResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, responses) -> None:
        self._responses = list(responses)

    async def execute(self, stmt, *args, **kwargs):
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_dashboard_returns_empty_risk_distribution_without_active_suggestion() -> None:
    db = _FakeDb(
        [
            _ScalarsResult(["SKU-1", "SKU-2", "SKU-3"]),
            _RowsResult([]),
            _ScalarOneOrNoneResult(
                SimpleNamespace(target_days=60, lead_time_days=50, restock_regions=[])
            ),
            _ScalarOneOrNoneResult(None),
            _RowsResult([]),
            _ScalarsResult([]),
            _RowsResult(
                [
                    ("SKU-1", "Alpha", None),
                    ("SKU-2", "Beta", "https://img.example/beta.png"),
                ]
            ),
        ]
    )

    async def _fake_run_step1(*_args, **_kwargs):
        return {
            "SKU-1": {"US": 1.0},
            "SKU-2": {"US": 1.0},
            "SKU-3": {"US": 1.0},
        }

    async def _fake_run_step2(*_args, **_kwargs):
        return (
            {
                "SKU-1": {"US": 10.0},
                "SKU-2": {"US": 35.0},
                "SKU-3": {"US": 70.0},
            },
            {},
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(metrics_module, "run_step1", _fake_run_step1)
    monkeypatch.setattr(metrics_module, "run_step2", _fake_run_step2)

    try:
        result = await build_dashboard_payload(db=db)  # type: ignore[arg-type]
    finally:
        monkeypatch.undo()

    assert result.enabled_sku_count == 3
    assert result.restock_sku_count == 3
    assert result.no_restock_sku_count == 0
    assert result.target_days == 60
    assert result.lead_time_days == 50
    assert result.suggestion_id is None
    assert result.urgent_count == 2
    assert result.warning_count == 0
    assert result.safe_count == 1
    assert result.risk_country_count == 1
    assert [item.model_dump() for item in result.country_risk_distribution] == [
        {
            "country": "US",
            "urgent_count": 2,
            "warning_count": 0,
            "safe_count": 1,
            "total_count": 3,
        }
    ]
    assert result.country_restock_distribution == []
    assert [item.model_dump() for item in result.top_urgent_skus] == [
        {
            "commodity_sku": "SKU-1",
            "commodity_name": "Alpha",
            "main_image": None,
            "country": "US",
            "sale_days": 10.0,
        },
        {
            "commodity_sku": "SKU-2",
            "commodity_name": "Beta",
            "main_image": "https://img.example/beta.png",
            "country": "US",
            "sale_days": 35.0,
        },
    ]


@pytest.mark.asyncio
async def test_dashboard_risk_distribution_uses_restock_regions_filter() -> None:
    db = _FakeDb(
        [
            _ScalarsResult(["SKU-1", "SKU-2"]),
            _RowsResult([]),
            _ScalarOneOrNoneResult(
                SimpleNamespace(target_days=60, lead_time_days=50, restock_regions=["EU"])
            ),
            _ScalarOneOrNoneResult(None),
            _RowsResult([]),
            _ScalarsResult([]),
            _RowsResult([("SKU-1", "Alpha", None)]),
        ]
    )

    async def _fake_run_step1(*_args, **_kwargs):
        return {
            "SKU-1": {"EU": 1.0, "DE": 1.0, "US": 1.0},
            "SKU-2": {"EU": 1.0, "DE": 1.0, "US": 1.0},
        }

    async def _fake_run_step2(*_args, **_kwargs):
        return (
            {
                "SKU-1": {"EU": 10.0, "DE": 10.0, "US": 10.0},
                "SKU-2": {"EU": 55.0, "DE": 10.0, "US": 10.0},
            },
            {},
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(metrics_module, "run_step1", _fake_run_step1)
    monkeypatch.setattr(metrics_module, "run_step2", _fake_run_step2)

    try:
        result = await build_dashboard_payload(db=db)  # type: ignore[arg-type]
    finally:
        monkeypatch.undo()

    assert result.risk_country_count == 1
    assert result.urgent_count == 1
    assert result.warning_count == 1
    assert result.safe_count == 0
    assert [item.model_dump() for item in result.country_risk_distribution] == [
        {
            "country": "EU",
            "urgent_count": 1,
            "warning_count": 1,
            "safe_count": 0,
            "total_count": 2,
        }
    ]
    assert [item.model_dump() for item in result.top_urgent_skus] == [
        {
            "commodity_sku": "SKU-1",
            "commodity_name": "Alpha",
            "main_image": None,
            "country": "EU",
            "sale_days": 10.0,
        }
    ]


@pytest.mark.asyncio
async def test_dashboard_restock_sku_count_uses_draft_demand_date() -> None:
    db = _FakeDb(
        [
            _ScalarsResult(["SKU-1"]),
            _RowsResult([]),
            _ScalarOneOrNoneResult(
                SimpleNamespace(target_days=60, lead_time_days=50, restock_regions=[])
            ),
            _ScalarOneOrNoneResult(
                SimpleNamespace(
                    id=9,
                    status="draft",
                    global_config_snapshot={
                        "demand_date": (date.today() + timedelta(days=30)).isoformat()
                    },
                )
            ),
            _RowsResult([]),
            _ScalarsResult([]),
            _ScalarsResult([]),
            _ScalarOneResult(0),
        ]
    )

    async def _fake_run_step1(*_args, **_kwargs):
        return {"SKU-1": {"US": 1.0}}

    async def _fake_run_step2(*_args, **_kwargs):
        return (
            {"SKU-1": {"US": 100.0}},
            {"SKU-1": {"US": SimpleNamespace(total=70)}},
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(metrics_module, "run_step1", _fake_run_step1)
    monkeypatch.setattr(metrics_module, "run_step2", _fake_run_step2)

    try:
        result = await build_dashboard_payload(db=db)  # type: ignore[arg-type]
    finally:
        monkeypatch.undo()

    assert result.restock_sku_count == 1
    assert result.no_restock_sku_count == 0


@pytest.mark.asyncio
async def test_dashboard_buckets_sale_days_by_country_using_global_thresholds() -> None:
    items = [
        SimpleNamespace(
            commodity_sku="SKU-1",
            sale_days_snapshot={"US": 10, "CA": 70},
            urgent=True,
            total_qty=12,
            country_breakdown={"US": 12, "CA": 4},
            procurement_export_status="pending",
            restock_export_status="pending",
        ),
        SimpleNamespace(
            commodity_sku="SKU-2",
            sale_days_snapshot={"US": 30, "CA": 15},
            urgent=False,
            total_qty=8,
            country_breakdown={"CA": 8},
            procurement_export_status="exported",
            restock_export_status="pending",
        ),
        SimpleNamespace(
            commodity_sku="SKU-3",
            sale_days_snapshot={"US": 60, "JP": 19},
            urgent=True,
            total_qty=5,
            country_breakdown={"JP": 5},
            procurement_export_status="pending",
            restock_export_status="pending",
        ),
        SimpleNamespace(
            commodity_sku="SKU-4",
            sale_days_snapshot=None,
            urgent=True,
            total_qty=3,
            country_breakdown={"US": 3},
            procurement_export_status="pending",
            restock_export_status="pending",
        ),
        SimpleNamespace(
            commodity_sku="SKU-5",
            sale_days_snapshot={"US": 25},
            urgent=False,
            total_qty=4,
            country_breakdown={"US": 4},
            procurement_export_status="pending",
            restock_export_status="pending",
        ),
        SimpleNamespace(
            commodity_sku="SKU-6",
            sale_days_snapshot={"CA": 65},
            urgent=False,
            total_qty=6,
            country_breakdown={"CA": 6, "JP": 2},
            procurement_export_status="pending",
            restock_export_status="pending",
        ),
        SimpleNamespace(
            commodity_sku="SKU-7",
            sale_days_snapshot={"US": 18, "CA": 12},
            urgent=True,
            total_qty=10,
            country_breakdown={"US": 4, "CA": 6},
            procurement_export_status="pending",
            restock_export_status="pending",
        ),
    ]
    db = _FakeDb(
        [
            _ScalarsResult(["SKU-1", "SKU-2", "SKU-3", "SKU-7"]),
            _RowsResult([]),
            _ScalarOneOrNoneResult(
                SimpleNamespace(target_days=60, lead_time_days=20, restock_regions=[])
            ),
            _ScalarOneOrNoneResult(SimpleNamespace(id=9, status="draft")),
            _RowsResult([]),
            _ScalarsResult([]),
            _RowsResult(
                [
                    ("SKU-1", "Alpha", None),
                    ("SKU-3", "Gamma", "https://img.example/gamma.png"),
                    ("SKU-7", "Delta", "https://img.example/delta.png"),
                ]
            ),
            _ScalarsResult(items),
            _ScalarOneResult(2),
        ]
    )

    async def _fake_run_step1(*_args, **_kwargs):
        return {
            "SKU-1": {"US": 1.0, "CA": 1.0},
            "SKU-2": {"US": 1.0, "CA": 1.0},
            "SKU-3": {"US": 1.0, "JP": 1.0},
            "SKU-7": {"US": 1.0, "CA": 1.0},
        }

    async def _fake_run_step2(*_args, **_kwargs):
        return (
            {
                "SKU-1": {"US": 10.0, "CA": 70.0},
                "SKU-2": {"US": 30.0, "CA": 15.0},
                "SKU-3": {"US": 60.0, "JP": 19.0},
                "SKU-7": {"US": 18.0, "CA": 12.0},
            },
            {},
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(metrics_module, "run_step1", _fake_run_step1)
    monkeypatch.setattr(metrics_module, "run_step2", _fake_run_step2)

    try:
        result = await build_dashboard_payload(db=db)  # type: ignore[arg-type]
    finally:
        monkeypatch.undo()

    assert result.suggestion_id == 9
    assert result.suggestion_snapshot_count == 2
    assert result.restock_sku_count == 4
    assert result.no_restock_sku_count == 0
    assert result.exported_count == 1
    assert result.urgent_count == 5
    assert result.warning_count == 1
    assert result.safe_count == 2
    assert result.risk_country_count == 3
    assert result.lead_time_days == 20
    assert result.target_days == 60
    assert [item.model_dump() for item in result.country_risk_distribution] == [
        {
            "country": "CA",
            "urgent_count": 2,
            "warning_count": 0,
            "safe_count": 1,
            "total_count": 3,
        },
        {
            "country": "JP",
            "urgent_count": 1,
            "warning_count": 0,
            "safe_count": 0,
            "total_count": 1,
        },
        {
            "country": "US",
            "urgent_count": 2,
            "warning_count": 1,
            "safe_count": 1,
            "total_count": 4,
        },
    ]
    assert [item.model_dump() for item in result.country_restock_distribution] == [
        {"country": "CA", "total_qty": 24},
        {"country": "US", "total_qty": 23},
        {"country": "JP", "total_qty": 7},
    ]
    assert [item.model_dump() for item in result.top_urgent_skus] == [
        {
            "commodity_sku": "SKU-1",
            "commodity_name": "Alpha",
            "main_image": None,
            "country": "US",
            "sale_days": 10.0,
        },
        {
            "commodity_sku": "SKU-7",
            "commodity_name": "Delta",
            "main_image": "https://img.example/delta.png",
            "country": "CA",
            "sale_days": 12.0,
        },
        {
            "commodity_sku": "SKU-2",
            "commodity_name": None,
            "main_image": None,
            "country": "CA",
            "sale_days": 15.0,
        },
        {
            "commodity_sku": "SKU-7",
            "commodity_name": "Delta",
            "main_image": "https://img.example/delta.png",
            "country": "US",
            "sale_days": 18.0,
        },
        {
            "commodity_sku": "SKU-3",
            "commodity_name": "Gamma",
            "main_image": "https://img.example/gamma.png",
            "country": "JP",
            "sale_days": 19.0,
        },
    ]
