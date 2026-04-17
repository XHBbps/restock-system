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
RESTOCK_EXPORT = "restock:export"
RESTOCK_NEW_CYCLE = "restock:new_cycle"

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
    PermDef(HOME_VIEW, "信息总览-查看", "信息总览"),
    PermDef(HOME_REFRESH, "信息总览-刷新", "信息总览"),
    PermDef(RESTOCK_VIEW, "补货发起-查看", "补货发起"),
    PermDef(RESTOCK_OPERATE, "补货发起-操作", "补货发起"),
    PermDef(RESTOCK_EXPORT, "补货发起-导出", "补货发起"),
    PermDef(RESTOCK_NEW_CYCLE, "补货发起-开启新一轮", "补货发起"),
    PermDef(HISTORY_VIEW, "历史记录-查看", "历史记录"),
    PermDef(HISTORY_DELETE, "历史记录-删除", "历史记录"),
    PermDef(DATA_BASE_VIEW, "基础数据-查看", "基础数据"),
    PermDef(DATA_BASE_EDIT, "基础数据-编辑", "基础数据"),
    PermDef(DATA_BIZ_VIEW, "业务数据-查看", "业务数据"),
    PermDef(SYNC_VIEW, "同步管理-查看", "同步管理"),
    PermDef(SYNC_OPERATE, "同步管理-操作", "同步管理"),
    PermDef(CONFIG_VIEW, "基础配置-查看", "基础配置"),
    PermDef(CONFIG_EDIT, "基础配置-编辑", "基础配置"),
    PermDef(MONITOR_VIEW, "系统监控-查看", "系统监控"),
    PermDef(AUTH_VIEW, "权限设置-查看", "权限设置"),
    PermDef(AUTH_MANAGE, "权限设置-管理", "权限设置"),
]

ALL_CODES: frozenset[str] = frozenset(p.code for p in REGISTRY)
