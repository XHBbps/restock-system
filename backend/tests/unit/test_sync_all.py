from app.sync.all import sync_all_job


class _FakeContext:
    def __init__(self) -> None:
        self.events: list[tuple[str | None, str | None, int | None]] = []

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.events.append((current_step, step_detail, total_steps))


async def test_sync_all_runs_steps_in_order(monkeypatch) -> None:
    import app.sync.all as sync_all_module

    called: list[str] = []

    async def _job_one(_ctx) -> None:
        called.append("one")

    async def _job_two(_ctx) -> None:
        called.append("two")

    monkeypatch.setattr(
        sync_all_module,
        "SYNC_ALL_STEPS",
        [("step 1", _job_one), ("step 2", _job_two)],
    )

    ctx = _FakeContext()
    await sync_all_job(ctx)  # type: ignore[arg-type]

    assert called == ["one", "two"]
    assert ctx.events[0] == ("全量同步", "开始执行 2 个同步任务", 2)
    assert ctx.events[1] == ("1/2", "执行 step 1", 2)
    assert ctx.events[2] == ("2/2", "执行 step 2", 2)
    assert ctx.events[-1] == ("完成", "已串行完成 2 个同步任务", 2)
