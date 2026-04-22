from pydantic import BaseModel, Field


class SchedulerJobOut(BaseModel):
    job_name: str
    next_run_time: str | None = None


class SchedulerStatusOut(BaseModel):
    enabled: bool
    running: bool
    timezone: str
    sync_interval_minutes: int
    jobs: list[SchedulerJobOut]


class SchedulerToggleIn(BaseModel):
    enabled: bool


class OrderDetailRefetchIn(BaseModel):
    days: int = Field(default=7, ge=1)
    shop_id: str | None = None


class OrderDetailRefetchOut(BaseModel):
    task_id: int | None = None
    existing: bool = False
    matched_count: int
    queued_count: int
    active_job_name: str | None = None
    active_trigger_source: str | None = None
