"""Services layer.

使用显式导入替代动态 __import__，确保 PyInstaller 冻结环境能正确分析依赖。
"""

# RBAC ORM 模型已迁移到 models/rbac.py，从那里重新导出保持兼容
from app.models.rbac import AccessLog
from app.models.rbac import RbacRole as Role  # noqa: F401
from app.models.rbac import (
    ResourceAccessControl,
    RolePermission,
    UserPermission,
    UserRole,
)

from .ai_service import AIServiceManager, ai_service_manager  # noqa: F401
from .analytics_service import AnalyticsService  # noqa: F401
from .backup_service import BackupService  # noqa: F401
from .cache_service import (
    CacheMetrics,
    CacheService,  # noqa: F401
    CacheStrategy,
    EntityCacheManager,
    cache_invalidate,
    cache_key,
    cache_result,
    cache_service,
    cached,
    metrics,
)
from .rbac_service import Permission, RBACService  # noqa: F401

# 加密服务（为测试兼容性提供别名）
try:
    from .encryption_service import DataPackageEncryption as EncryptionService  # noqa: F401
except ImportError:  # pragma: no cover
    EncryptionService = None  # type: ignore[assignment]

# RATE_LIMITS 已移至 app.core.security 模块的 check_rate_limit() 函数管理
# 保留空 dict 以防外部依赖
RATE_LIMITS: dict = {}

__all__ = [
    # cache_service
    "CacheStrategy",
    "CacheService",
    "CacheMetrics",
    "EntityCacheManager",
    "cache_key",
    "cached",
    "cache_result",
    "cache_invalidate",
    "cache_service",
    "metrics",
    # backup_service
    "BackupService",
    # rbac_service
    "Permission",
    "Role",
    "UserPermission",
    "RolePermission",
    "UserRole",
    "ResourceAccessControl",
    "AccessLog",
    "RBACService",
    # ai_service
    "AIServiceManager",
    "ai_service_manager",
    # analytics_service
    "AnalyticsService",
]
