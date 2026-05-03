from datetime import datetime

import pytest


class _FakeTrigger:
    def __init__(self, next_run_time: datetime) -> None:
        self.next_run_time = next_run_time

    def get_next_fire_time(self, previous_fire_time, now):
        return self.next_run_time


class _FakeJob:
    def __init__(
        self,
        job_name: str,
        next_run_time: datetime | None,
        trigger: _FakeTrigger | None = None,
    ) -> None:
        self.args = [job_name]
        self.id = f"trigger_{job_name}"
        self.next_run_time = next_run_time
        self.trigger = trigger


class _FakeScheduler:
    def __init__(self, *, running: bool, jobs: list[_FakeJob] | None = None) -> None:
        self.running = running
        self._jobs = jobs or []

    def get_jobs(self) -> list[_FakeJob]:
        return self._jobs

    def start(self) -> None:
        self.running = True

    def shutdown(self, wait: bool = False) -> None:
        self.running = False


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
        )

    monkeypatch.setattr(scheduler_module, "setup_scheduler", fake_setup_scheduler)
    monkeypatch.setattr(scheduler_module, "_load_scheduler_config", fake_load_scheduler_config)

    status = await scheduler_module.scheduler_status()

    assert status.enabled is False
    assert status.running is False
    assert status.sync_interval_minutes == 45
    assert status.jobs[0].job_name == "sync_inventory"
    assert status.jobs[0].next_run_time is None


@pytest.mark.asyncio
async def test_scheduler_status_calculates_next_run_for_backend_process(monkeypatch) -> None:
    import app.tasks.scheduler as scheduler_module

    expected_next_run = datetime(2026, 4, 9, 13, 0, 0)
    fake_scheduler = _FakeScheduler(
        running=False,
        jobs=[_FakeJob("sync_shop", None, trigger=_FakeTrigger(expected_next_run))],
    )

    async def fake_setup_scheduler(*, force_reload: bool = False):
        return fake_scheduler

    async def fake_load_scheduler_config():
        return scheduler_module.SchedulerRuntimeConfig(
            enabled=True,
            sync_interval_minutes=60,
        )

    monkeypatch.setattr(scheduler_module, "setup_scheduler", fake_setup_scheduler)
    monkeypatch.setattr(scheduler_module, "_load_scheduler_config", fake_load_scheduler_config)

    status = await scheduler_module.scheduler_status()

    assert status.running is False
    assert status.jobs[0].job_name == "sync_shop"
    assert status.jobs[0].next_run_time == "2026-04-09T13:00:00"


def test_register_jobs_includes_shop_daily_sync() -> None:
    import app.tasks.scheduler as scheduler_module

    scheduler = scheduler_module._build_scheduler()
    scheduler_module._register_jobs(scheduler, sync_interval_minutes=60)

    jobs_by_name = {job.args[0]: job for job in scheduler.get_jobs()}

    assert "sync_shop" in jobs_by_name
    assert jobs_by_name["sync_shop"].trigger.get_next_fire_time(
        None,
        datetime(2026, 4, 9, 2, 59, 0, tzinfo=scheduler_module.BEIJING),
    ) == datetime(2026, 4, 9, 3, 0, 0, tzinfo=scheduler_module.BEIJING)


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
    fake_scheduler = _FakeScheduler(running=True)

    async def fake_reload_scheduler():
        return sync_api_module.SchedulerStatusOut(
            enabled=fake_scheduler.running,
            running=fake_scheduler.running,
            timezone="Asia/Shanghai",
            sync_interval_minutes=60,
            jobs=[],
        )

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
    fake_scheduler = _FakeScheduler(running=False)

    async def fake_reload_scheduler():
        return sync_api_module.SchedulerStatusOut(
            enabled=fake_scheduler.running,
            running=fake_scheduler.running,
            timezone="Asia/Shanghai",
            sync_interval_minutes=60,
            jobs=[],
        )

    monkeypatch.setattr(sync_api_module, "reload_scheduler", fake_reload_scheduler)

    result = await sync_api_module.set_scheduler_status(
        sync_api_module.SchedulerToggleIn(enabled=False),
        db=fake_db,
        _={},
    )

    assert fake_db.committed is True
    assert result.enabled is False
