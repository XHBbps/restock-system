"""简易 metrics 端点（非 Prometheus，文本格式）。

返回 task_run 各状态计数 + 最近 24h 同步成功率，用于人工巡检。
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.core.timezone import now_beijing
from app.models.api_call_log import ApiCallLog
from app.models.task_run import TaskRun

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> str:
    # task_run 状态分布
    rows = (
        await db.execute(select(TaskRun.status, func.count()).group_by(TaskRun.status))
    ).all()
    task_status_lines = [f"task_run_status{{status=\"{s}\"}} {n}" for s, n in rows]

    # 24h 同步成功率
    since = now_beijing() - timedelta(hours=24)
    api_rows = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((ApiCallLog.saihu_code == 0, 1), else_=0)).label("succ"),
            ).where(ApiCallLog.called_at >= since)
        )
    ).one()
    total = int(api_rows[0] or 0)
    succ = int(api_rows[1] or 0)
    rate = (succ / total) if total else 0.0

    lines = [
        "# HELP task_run_status TaskRun count by status",
        "# TYPE task_run_status gauge",
        *task_status_lines,
        "",
        "# HELP saihu_api_calls_24h Total Saihu API calls in last 24h",
        "# TYPE saihu_api_calls_24h gauge",
        f"saihu_api_calls_24h {total}",
        "",
        "# HELP saihu_api_success_rate_24h Success rate of Saihu API calls",
        "# TYPE saihu_api_success_rate_24h gauge",
        f"saihu_api_success_rate_24h {rate:.4f}",
        "",
    ]
    return "\n".join(lines)
