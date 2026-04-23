"""Tripwire：GlobalConfig 所有列必须被分类为 SENSITIVE 或 NEUTRAL。

新增字段时如果忘记分类，此测试会红，迫使开发者想清楚：
- 改这个值需要 dashboard refresh 吗？→ 加入 SENSITIVE
- 纯运行时配置 / 审计字段？→ 加入 NEUTRAL
"""

from __future__ import annotations

from app.api.config import (
    GLOBAL_CONFIG_NEUTRAL_FIELDS,
    GLOBAL_CONFIG_SENSITIVE_FIELDS,
)
from app.models.global_config import GlobalConfig


def test_every_global_config_column_is_classified() -> None:
    all_mapped_columns = {col.key for col in GlobalConfig.__table__.columns}
    classified = GLOBAL_CONFIG_SENSITIVE_FIELDS | GLOBAL_CONFIG_NEUTRAL_FIELDS

    unclassified = all_mapped_columns - classified
    assert not unclassified, (
        f"GlobalConfig 新增了未分类字段 {unclassified}。请决定：\n"
        f"  - 改此字段是否应触发 dashboard_snapshot.stale=True？\n"
        f"    是 → 加入 GLOBAL_CONFIG_SENSITIVE_FIELDS\n"
        f"    否 → 加入 GLOBAL_CONFIG_NEUTRAL_FIELDS"
    )


def test_no_field_is_classified_twice() -> None:
    overlap = GLOBAL_CONFIG_SENSITIVE_FIELDS & GLOBAL_CONFIG_NEUTRAL_FIELDS
    assert not overlap, f"字段同时出现在 SENSITIVE 和 NEUTRAL：{overlap}"


def test_classified_fields_all_exist_on_model() -> None:
    all_mapped_columns = {col.key for col in GlobalConfig.__table__.columns}
    classified = GLOBAL_CONFIG_SENSITIVE_FIELDS | GLOBAL_CONFIG_NEUTRAL_FIELDS

    stale_classifications = classified - all_mapped_columns
    assert not stale_classifications, (
        f"SENSITIVE/NEUTRAL 列表里有 model 上已不存在的字段："
        f"{stale_classifications}。请清理过时分类。"
    )
