"""端到端引擎集成测试。"""
import pytest


class _TestContext:
    """Minimal JobContext for testing."""
    def __init__(self):
        self.steps = []
        self.payload = {"triggered_by": "test"}

    async def progress(self, **kwargs):
        self.steps.append(kwargs.get("current_step", ""))


@pytest.mark.asyncio
class TestEngineE2E:
    pass
