from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.core.timezone import now_beijing
from app.schemas.sync import EngineRunIn


def test_engine_run_schema_accepts_today_or_future_demand_date() -> None:
    today = now_beijing().date()

    assert EngineRunIn(demand_date=today).demand_date == today
    assert EngineRunIn(demand_date=today + timedelta(days=1)).demand_date == today + timedelta(
        days=1
    )


def test_engine_run_schema_rejects_past_demand_date() -> None:
    with pytest.raises(ValidationError):
        EngineRunIn(demand_date=now_beijing().date() - timedelta(days=1))
