"""权限注册表 — 系统所有权限码的唯一真相源。

REGISTRY 列表顺序即前端展示顺序；ALL_CODES 用于快速校验。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermDef:
    """单条权限定义。"""

    code: str
    name: str
    group_name: str


# ── 权限码常量 ──────────────────────────────────────────────

HOME_VIEW = "home:view"
HOME_REFRESH = "home:refresh"

RESTOCK_VIEW = "restock:view"
RESTOCK_OPERATE = "restock:operate"

HISTORY_VIEW = "history:view"
HISTORY_DELETE = "history:delete"

DATA_BASE_VIEW = "data_base:view"
DATA_BASE_EDIT = "data_base:edit"

DATA_BIZ_VIEW = "data_biz:view"

SYNC_VIEW = "sync:view"
SYNC_OPERATE = "sync:operate"

CONFIG_VIEW = "config:view"
CONFIG_EDIT = "config:edit"

MONITOR_VIEW = "monitor:view"

AUTH_VIEW = "auth:view"
AUTH_MANAGE = "auth:manage"

# ── 注册表（列表顺序 = 前端展示顺序）───────────────────────

REGISTRY: list[PermDef] = [
    PermDef(HOME_VIEW, "查看信息总览", "信息总览"),
    PermDef(HOME_REFRESH, "刷新信息总览", "信息总览"),
    PermDef(RESTOCK_VIEW, "查看补货发起", "补货发起"),
    PermDef(RESTOCK_OPERATE, "操作补货发起", "补货发起"),
    PermDef(HISTORY_VIEW, "查看历史记录", "历史记录"),
    PermDef(HISTORY_DELETE, "删除历史记录", "历史记录"),
    PermDef(DATA_BASE_VIEW, "查看基础数据", "基础数据"),
    PermDef(DATA_BASE_EDIT, "编辑基础数据", "基础数据"),
    PermDef(DATA_BIZ_VIEW, "查看业务数据", "业务数据"),
    PermDef(SYNC_VIEW, "查看同步管理", "同步管理"),
    PermDef(SYNC_OPERATE, "操作同步管理", "同步管理"),
    PermDef(CONFIG_VIEW, "查看基础配置", "基础配置"),
    PermDef(CONFIG_EDIT, "编辑基础配置", "基础配置"),
    PermDef(MONITOR_VIEW, "查看系统监控", "系统监控"),
    PermDef(AUTH_VIEW, "查看权限设置", "权限设置"),
    PermDef(AUTH_MANAGE, "管理权限设置", "权限设置"),
]

ALL_CODES: frozenset[str] = frozenset(p.code for p in REGISTRY)
