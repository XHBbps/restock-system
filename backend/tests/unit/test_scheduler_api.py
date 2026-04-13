from datetime import datetime
from types import SimpleNamespace

import pytest


class _FakeJob:
    def __init__(self, job_name: str, next_run_time: datetime | None) -> None:
        self.args = [job_name]
        self.id = f"trigger_{job_name}"
        self.next_run_time = next_run_time


class _FakeScheduler:
    def __init__(self, *, running: bool, jobs: list[_FakeJob] | None = None) -> None:
        self.running = running
        self._jobs = jobs or []
        self.start_calls = 0
        self.shutdown_calls = 0

    def get_jobs(self) -> list[_FakeJob]:
        return self._jobs

    def start(self) -> None:
        self.running = True
        self.start_calls += 1

    def shutdown(self, wait: bool = False) -> None:
        self.running = False
        self.shutdown_calls += 1


@pytest.mark.asyncio
async def test_scheduler_status_returns_stable_payload(monkeypatch) -> None:
    import app.tasks.scheduler as scheduler_module

    fake_scheduler = _FakeScheduler(
        running=False,
        jobs=[_FakeJob("sync_inventory", datetime(2026, 4, 9, 12, 0, 0))],
    )

    async def fake_setup_scheduler(*, force_reload: bool = False):
        return fake_scheduler

    async def fake_load_scheduler_config():
        return scheduler_module.SchedulerRuntimeConfig(
            enabled=False,
            sync_interval_minutes=45,
            calc_cron="0 9 * * *",
            calc_enabled=True,
        )

    monkeypatch.setattr(scheduler_module, "setup_scheduler", fake_setup_scheduler)
    monkeypatch.setattr(scheduler_module, "_load_scheduler_config", fake_load_scheduler_config)

    status = await scheduler_module.scheduler_status()

    assert status.enabled is False
    assert status.running is False
    assert status.sync_interval_minutes == 45
    assert status.calc_cron == "0 9 * * *"
    assert status.jobs[0].job_name == "sync_inventory"
    assert status.jobs[0].next_run_time == "2026-04-09T12:00:00"


@pytest.mark.asyncio
async def test_set_scheduler_status_starts_scheduler(monkeypatch) -> None:
    import app.api.sync as sync_api_module

    class _FakeDb:
        def __init__(self) -> None:
            self.executed = []
            self.committed = False

        async def execute(self, stmt) -> None:
            self.executed.append(stmt)

        async def commit(self) -> None:
            self.committed = True

    fake_db = _FakeDb()

    async def fake_reload_scheduler():
        return sync_api_module.SchedulerStatusOut(
            enabled=fake_scheduler.running,
            running=fake_scheduler.running,
            timezone="Asia/Shanghai",
            sync_interval_minutes=60,
            calc_cron="0 8 * * *",
            jobs=[],
        )

    fake_scheduler = _FakeScheduler(running=True)
    monkeypatch.setattr(sync_api_module, "reload_scheduler", fake_reload_scheduler)

    result = await sync_api_module.set_scheduler_status(
        sync_api_module.SchedulerToggleIn(enabled=True),
        db=fake_db,
        _={},
    )

    assert fake_db.committed is True
    assert result.enabled is True


@pytest.mark.asyncio
async def test_set_scheduler_status_stops_scheduler(monkeypatch) -> None:
    import app.api.sync as sync_api_module

    class _FakeDb:
        def __init__(self) -> None:
            self.executed = []
            self.committed = False

        async def execute(self, stmt) -> None:
            self.executed.append(stmt)

        async def commit(self) -> None:
            self.committed = True

    fake_db = _FakeDb()

    async def fake_reload_scheduler():
        return sync_api_module.SchedulerStatusOut(
            enabled=fake_scheduler.running,
            running=fake_scheduler.running,
            timezone="Asia/Shanghai",
            sync_interval_minutes=60,
            calc_cron="0 8 * * *",
            jobs=[],
        )

    fake_scheduler = _FakeScheduler(running=False)
    monkeypatch.setattr(sync_api_module, "reload_scheduler", fake_reload_scheduler)

    result = await sync_api_module.set_scheduler_status(
        sync_api_module.SchedulerToggleIn(enabled=False),
        db=fake_db,
        _={},
    )

    assert fake_db.committed is True
    assert result.enabled is False


@pytest.mark.asyncio
async def test_refetch_order_detail_returns_empty_when_no_targets(monkeypatch) -> None:
    import app.api.sync as sync_api_module

    class _FakeDb:
        pass

    async def fake_get_active_order_detail_task(_db):
        return None

    async def fake_find_refetch_targets(*_args, **_kwargs):
        return []

    enqueue = pytest.fail
    monkeypatch.setattr(sync_api_module, "_get_active_order_detail_task", fake_get_active_order_detail_task)
    monkeypatch.setattr(sync_api_module, "find_refetch_targets", fake_find_refetch_targets)
    monkeypatch.setattr(sync_api_module, "enqueue_task", enqueue)

    result = await sync_api_module.refetch_order_detail(
        sync_api_module.OrderDetailRefetchIn(days=7, limit=50, shop_id=None),
        db=_FakeDb(),  # type: ignore[arg-type]
        _={},
    )

    assert result.task_id is None
    assert result.matched_count == 0
    assert result.queued_count == 0
    assert result.truncated is False
    assert result.active_job_name is None
    assert result.active_trigger_source is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("job_name", "trigger_source"),
    [
        ("refetch_order_detail", "manual"),
        ("sync_order_detail", "scheduler"),
        ("sync_all", "manual"),
    ],
)
async def test_refetch_order_detail_reuses_active_conflict_task(monkeypatch, job_name: str, trigger_source: str) -> None:
    import app.api.sync as sync_api_module

    class _FakeDb:
        pass

    async def fake_get_active_order_detail_task(_db):
        return SimpleNamespace(id=88, job_name=job_name, trigger_source=trigger_source)

    monkeypatch.setattr(sync_api_module, "_get_active_order_detail_task", fake_get_active_order_detail_task)
    monkeypatch.setattr(sync_api_module, "find_refetch_targets", pytest.fail)
    monkeypatch.setattr(sync_api_module, "enqueue_task", pytest.fail)

    result = await sync_api_module.refetch_order_detail(
        sync_api_module.OrderDetailRefetchIn(days=7, limit=50, shop_id=None),
        db=_FakeDb(),  # type: ignore[arg-type]
        _={},
    )

    assert result.task_id == 88
    assert result.existing is True
    assert result.matched_count == 0
    assert result.queued_count == 0
    assert result.truncated is False
    assert result.active_job_name == job_name
    assert result.active_trigger_source == trigger_source


@pytest.mark.asyncio
async def test_refetch_order_detail_enqueues_trimmed_targets(monkeypatch) -> None:
    import app.api.sync as sync_api_module

    class _FakeDb:
        pass

    async def fake_get_active_order_detail_task(_db):
        return None

    async def fake_find_refetch_targets(*_args, **_kwargs):
        return [
            ("shop-1", "order-1"),
            ("shop-2", "order-2"),
            ("shop-3", "order-3"),
        ]

    async def fake_enqueue_task(_db, *, job_name, trigger_source, dedupe_key=None, payload=None, priority=100):
        assert job_name == sync_api_module.REFETCH_JOB_NAME
        assert trigger_source == "manual"
        assert dedupe_key == sync_api_module.REFETCH_JOB_NAME
        assert payload == {
            "days": 7,
            "limit": 2,
            "shop_id": "shop-1",
            "targets": [
                {"shop_id": "shop-1", "amazon_order_id": "order-1"},
                {"shop_id": "shop-2", "amazon_order_id": "order-2"},
            ],
        }
        assert priority == 100
        return 99, False

    monkeypatch.setattr(sync_api_module, "_get_active_order_detail_task", fake_get_active_order_detail_task)
    monkeypatch.setattr(sync_api_module, "find_refetch_targets", fake_find_refetch_targets)
    monkeypatch.setattr(sync_api_module, "enqueue_task", fake_enqueue_task)

    result = await sync_api_module.refetch_order_detail(
        sync_api_module.OrderDetailRefetchIn(days=7, limit=2, shop_id="shop-1"),
        db=_FakeDb(),  # type: ignore[arg-type]
        _={},
    )

    assert result.task_id == 99
    assert result.existing is False
    assert result.matched_count == 2
    assert result.queued_count == 2
    assert result.truncated is True
    assert result.active_job_name is None
    assert result.active_trigger_source is None
