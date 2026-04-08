"""Job 注册表：job_name → 异步执行函数。

Worker 通过 `JOB_REGISTRY[task.job_name]` 找到要执行的函数。
Phase 2 仅注册 placeholder；Phase 3+ 由各 sync/engine/pushback 模块注册。
"""

from collections.abc import Awaitable, Callable
from typing import Any

JobHandler = Callable[["JobContext"], Awaitable[None]]


class JobContext:
    """Job 执行上下文，封装进度更新与 payload 访问。"""

    def __init__(
        self,
        task_id: int,
        job_name: str,
        payload: dict[str, Any],
        progress_setter: Callable[..., Awaitable[None]],
    ) -> None:
        self.task_id = task_id
        self.job_name = job_name
        self.payload = payload
        self._set_progress = progress_setter

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        await self._set_progress(
            current_step=current_step,
            step_detail=step_detail,
            total_steps=total_steps,
        )


JOB_REGISTRY: dict[str, JobHandler] = {}


def register(job_name: str) -> Callable[[JobHandler], JobHandler]:
    """装饰器：把函数注册到 JOB_REGISTRY。"""

    def decorator(fn: JobHandler) -> JobHandler:
        JOB_REGISTRY[job_name] = fn
        return fn

    return decorator


# Phase 2 占位：echo 任务用于联调
@register("echo")
async def _echo(ctx: JobContext) -> None:
    await ctx.progress(current_step="echo", step_detail=str(ctx.payload), total_steps=1)
