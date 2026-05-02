import pytest


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post(self, endpoint: str, body: dict[str, str]):
        self.calls.append((endpoint, body))
        page_no = int(body["pageNo"])
        rows = [{"sku": f"SKU-{page_no}"}] if page_no <= 2 else []
        return {"data": {"rows": rows, "totalPage": 2}}


@pytest.mark.asyncio
async def test_list_commodities_uses_unfiltered_pagination(monkeypatch) -> None:
    import app.saihu.endpoints.commodity as commodity_module

    client = _FakeClient()
    page_events: list[tuple[int, int, int]] = []

    async def _on_page(page_no: int, total_page: int, rows_count: int) -> None:
        page_events.append((page_no, total_page, rows_count))

    monkeypatch.setattr(commodity_module, "get_saihu_client", lambda: client)

    rows = [row async for row in commodity_module.list_commodities(on_page=_on_page)]

    assert rows == [{"sku": "SKU-1"}, {"sku": "SKU-2"}]
    assert client.calls == [
        ("/api/commodity/pageList.json", {"pageNo": "1", "pageSize": "100"}),
        ("/api/commodity/pageList.json", {"pageNo": "2", "pageSize": "100"}),
    ]
    assert page_events == [(1, 2, 1), (2, 2, 1)]
