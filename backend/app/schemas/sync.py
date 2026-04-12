from pydantic import BaseModel


class SchedulerJobOut(BaseModel):
    job_name: str
    next_run_time: str | None = None


class SchedulerStatusOut(BaseModel):
    enabled: bool
    running: bool
    timezone: str
    sync_interval_minutes: int
    calc_cron: str
    jobs: list[SchedulerJobOut]


class SchedulerToggleIn(BaseModel):
    enabled: bool
