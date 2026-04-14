from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest


class _FakeCtx:
    def __init__(self) -> None:
        self.steps: list[tuple[str | None, str | None, int | None]] = []

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.steps.append((current_step, step_detail, total_steps))


@pytest.mark.asyncio
async def test_refresh_dashboard_snapshot_job_marks_ready(monkeypatch) -> None:
    import app.tasks.jobs.dashboard_snapshot as job_module

    calls: list[tuple[str, object | None]] = []

    @asynccontextmanager
    async def _fake_session_factory():
        yield SimpleNamespace()

    async def _fake_build_dashboard_payload(_db):
        return SimpleNamespace(model_dump=lambda: {"urgent_count": 3})

    async def _fake_mark_refreshing():
        calls.append(("refreshing", None))

    async def _fake_mark_ready(payload):
        calls.append(("ready", payload))

    monkeypatch.setattr(job_module, "async_session_factory", _fake_session_factory)
    monkeypatch.setattr(job_module, "build_dashboard_payload", _fake_build_dashboard_payload)
    monkeypatch.setattr(job_module, "_mark_refreshing", _fake_mark_refreshing)
    monkeypatch.setattr(job_module, "_mark_ready", _fake_mark_ready)
    monkeypatch.setattr(job_module, "_mark_failed", pytest.fail)

    ctx = _FakeCtx()
    await job_module.refresh_dashboard_snapshot_job(ctx)  # type: ignore[arg-type]

    assert calls == [
        ("refreshing", None),
        ("ready", {"urgent_count": 3}),
    ]
    assert ctx.steps[-1][1] == "信息总览快照已更新"


@pytest.mark.asyncio
async def test_refresh_dashboard_snapshot_job_marks_failed(monkeypatch) -> None:
    import app.tasks.jobs.dashboard_snapshot as job_module

    calls: list[tuple[str, object | None]] = []

    @asynccontextmanager
    async def _fake_session_factory():
        yield SimpleNamespace()

    async def _fake_build_dashboard_payload(_db):
        raise RuntimeError("boom")

    async def _fake_mark_refreshing():
        calls.append(("refreshing", None))

    async def _fake_mark_failed(error):
        calls.append(("failed", error))

    monkeypatch.setattr(job_module, "async_session_factory", _fake_session_factory)
    monkeypatch.setattr(job_module, "build_dashboard_payload", _fake_build_dashboard_payload)
    monkeypatch.setattr(job_module, "_mark_refreshing", _fake_mark_refreshing)
    monkeypatch.setattr(job_module, "_mark_ready", pytest.fail)
    monkeypatch.setattr(job_module, "_mark_failed", _fake_mark_failed)

    ctx = _FakeCtx()
    with pytest.raises(RuntimeError, match="boom"):
        await job_module.refresh_dashboard_snapshot_job(ctx)  # type: ignore[arg-type]

    assert calls == [
        ("refreshing", None),
        ("failed", "boom"),
    ]
