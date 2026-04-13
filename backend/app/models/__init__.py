"""ORM 模型聚合入口。

Alembic env.py 通过 `from app.models import *` 触发所有模型注册到 Base.metadata。
"""

from app.models.access_token import AccessTokenCache
from app.models.api_call_log import ApiCallLog
from app.models.global_config import GlobalConfig
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotHistory, InventorySnapshotLatest
from app.models.login_attempt import LoginAttempt
from app.models.order import OrderDetail, OrderDetailFetchLog, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.models.shop import Shop
from app.models.sku import SkuConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.sync_state import SyncState
from app.models.task_run import TaskRun
from app.models.warehouse import Warehouse
from app.models.zipcode_rule import ZipcodeRule

__all__ = [
    "AccessTokenCache",
    "ApiCallLog",
    "GlobalConfig",
    "InTransitItem",
    "InTransitRecord",
    "InventorySnapshotHistory",
    "InventorySnapshotLatest",
    "LoginAttempt",
    "OrderDetail",
    "OrderDetailFetchLog",
    "OrderHeader",
    "OrderItem",
    "ProductListing",
    "Shop",
    "SkuConfig",
    "Suggestion",
    "SuggestionItem",
    "SyncState",
    "TaskRun",
    "Warehouse",
    "ZipcodeRule",
]
