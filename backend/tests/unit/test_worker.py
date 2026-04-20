import asyncio

import pytest

import app.tasks.worker as worker_module
from app.tasks.worker import TaskLeaseLostError, Worker


class _FakeUpdateResult:
    rowcount = 0


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, *_args, **_kwargs):
        return _FakeUpdateResult()

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_progress_setter_raises_when_worker_no_longer_owns_task(monkeypatch) -> None:
    monkeypatch.setattr(worker_module, "async_session_factory", lambda: _FakeSession())

    worker = Worker()
    lease_lost = asyncio.Event()
    progress_setter = worker._make_progress_setter(123, lease_lost)

    with pytest.raises(TaskLeaseLostError):
        await progress_setter(current_step="export")

    assert lease_lost.is_set()
