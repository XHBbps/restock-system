from datetime import date

from pydantic import BaseModel, field_validator

from app.core.timezone import now_beijing


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


class EngineRunIn(BaseModel):
    demand_date: date

    @field_validator("demand_date")
    @classmethod
    def demand_date_must_not_be_past(cls, value: date) -> date:
        if value < now_beijing().date():
            raise ValueError("补货日期不能早于今天")
        return value
