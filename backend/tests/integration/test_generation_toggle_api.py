"""Integration tests for generation-toggle APIs."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_config import GlobalConfig
from app.models.suggestion import Suggestion
from tests.integration.factories import seed_global_config


@pytest.mark.asyncio
async def test_get_generation_toggle_returns_current_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, suggestion_generation_enabled=False)
    await db_session.commit()

    resp = await client.get("/api/config/generation-toggle")

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["updated_by"] is None
    assert body["updated_by_name"] is None
    assert body["updated_at"] is None


@pytest.mark.asyncio
async def test_patch_generation_toggle_on_archives_draft_suggestions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, suggestion_generation_enabled=False)
    # draft + archived + error 各一
    s_draft = Suggestion(
        status="draft",
        global_config_snapshot={},
        total_items=0,
        triggered_by="manual",
    )
    s_archived = Suggestion(
        status="archived",
        global_config_snapshot={},
        total_items=0,
        triggered_by="manual",
    )
    s_error = Suggestion(
        status="error",
        global_config_snapshot={},
        total_items=0,
        triggered_by="manual",
    )
    db_session.add_all([s_draft, s_archived, s_error])
    await db_session.commit()
    draft_id = s_draft.id
    archived_id = s_archived.id
    error_id = s_error.id

    resp = await client.patch("/api/config/generation-toggle", json={"enabled": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["updated_by"] == 1
    assert body["updated_at"] is not None

    # PATCH 在另一个 session 里提交,清掉本 session 的 identity-map 缓存
    db_session.expire_all()
    # draft 被归档，其他状态不变
    rows = {
        r.id: r
        for r in (
            await db_session.execute(
                select(Suggestion).where(Suggestion.id.in_([draft_id, archived_id, error_id]))
            )
        )
        .scalars()
        .all()
    }
    assert rows[draft_id].status == "archived"
    assert rows[draft_id].archived_trigger == "admin_toggle"
    assert rows[draft_id].archived_by == 1
    assert rows[draft_id].archived_at is not None
    assert rows[archived_id].status == "archived"
    assert rows[archived_id].archived_trigger is None
    assert rows[error_id].status == "error"


@pytest.mark.asyncio
async def test_patch_generation_toggle_off_does_not_archive(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, suggestion_generation_enabled=True)
    s_draft = Suggestion(
        status="draft",
        global_config_snapshot={},
        total_items=0,
        triggered_by="manual",
    )
    db_session.add(s_draft)
    await db_session.commit()
    draft_id = s_draft.id

    resp = await client.patch("/api/config/generation-toggle", json={"enabled": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False

    # 翻 OFF 时 draft 保留不动
    row = (
        await db_session.execute(select(Suggestion).where(Suggestion.id == draft_id))
    ).scalar_one()
    assert row.status == "draft"
    assert row.archived_trigger is None

    # global_config 被更新
    cfg = (await db_session.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
    assert cfg.suggestion_generation_enabled is False
    assert cfg.generation_toggle_updated_by == 1
    assert cfg.generation_toggle_updated_at is not None
