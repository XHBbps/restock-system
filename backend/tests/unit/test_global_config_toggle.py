from app.models.global_config import GlobalConfig


def test_toggle_fields():
    cols = {c.name for c in GlobalConfig.__table__.columns}
    assert "suggestion_generation_enabled" in cols
    assert "generation_toggle_updated_by" in cols
    assert "generation_toggle_updated_at" in cols
