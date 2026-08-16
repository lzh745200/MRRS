"""
API v1 路由模块
注册所有业务路由

注意：子模块包使用显式静态导入确保 PyInstaller 能正确打包；
业务模块使用 importlib 动态导入，保持代码简洁。
"""

import importlib
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# 确保 PyInstaller 环境也能看到路由加载日志
if not logger.handlers:
    from app.core.config import settings

    _log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    _console = logging.StreamHandler()
    _console.setLevel(_log_level)
    _console.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_console)
    logger.setLevel(_log_level)

api_v1_router = APIRouter(prefix="/api/v1")

# ==================== 显式静态导入所有路由模块 ====================
# 使用静态导入而非动态导入，确保 PyInstaller 能正确收集所有模块

# ---- 子模块包 ----
try:
    from app.api.v1.auth import router as auth_router
    api_v1_router.include_router(auth_router)
    logger.debug("已加载路由: auth")
except Exception as e:
    logger.warning("加载 auth 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.data import router as data_router
    api_v1_router.include_router(data_router)
    logger.debug("已加载路由: data")
except Exception as e:
    logger.warning("加载 data 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.import_export import router as import_export_router
    api_v1_router.include_router(import_export_router)
    logger.debug("已加载路由: import_export")
except Exception as e:
    logger.warning("加载 import_export 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.system import router as system_router
    api_v1_router.include_router(system_router)
    logger.debug("已加载路由: system")
except Exception as e:
    logger.warning("加载 system 路由失败: %s", e, exc_info=True)

# ---- System 子模块 ----
try:
    from app.api.v1.system import health as system_health_module
    if hasattr(system_health_module, 'router'):
        api_v1_router.include_router(system_health_module.router)
        logger.debug("已加载路由: system.health")
except Exception as e:
    logger.warning("加载 system.health 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.system import env as system_env_module
    if hasattr(system_env_module, 'router'):
        api_v1_router.include_router(system_env_module.router)
        logger.debug("已加载路由: system.env")
except Exception as e:
    logger.warning("加载 system.env 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.system import config_package as system_config_package_module
    if hasattr(system_config_package_module, 'router'):
        api_v1_router.include_router(system_config_package_module.router)
        logger.debug("已加载路由: system.config_package")
except Exception as e:
    logger.warning("加载 system.config_package 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.monitoring import metrics as monitoring_metrics_module
    if hasattr(monitoring_metrics_module, 'router'):
        api_v1_router.include_router(monitoring_metrics_module.router)
        logger.debug("已加载路由: monitoring.metrics")
except Exception as e:
    logger.warning("加载 monitoring.metrics 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.monitoring import secrets as monitoring_secrets_module
    if hasattr(monitoring_secrets_module, 'router'):
        api_v1_router.include_router(monitoring_secrets_module.router)
        logger.debug("已加载路由: monitoring.secrets")
except Exception as e:
    logger.warning("加载 monitoring.secrets 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.monitoring import data_tier as monitoring_data_tier_module
    if hasattr(monitoring_data_tier_module, 'router'):
        api_v1_router.include_router(monitoring_data_tier_module.router)
        logger.debug("已加载路由: monitoring.data_tier")
except Exception as e:
    logger.warning("加载 monitoring.data_tier 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.messages import notifications_router
    api_v1_router.include_router(notifications_router)
    logger.debug("已加载路由: notifications")
except Exception as e:
    logger.warning("加载 notifications 路由失败: %s", e, exc_info=True)

try:
    from app.api.v1.reminders import router as reminders_router
    api_v1_router.include_router(reminders_router)
    logger.debug("已加载路由: reminders")
except Exception as e:  # pragma: no cover - 防御性分支：reminders 模块随包安装必然存在
    logger.warning("加载 reminders 路由失败: %s", e, exc_info=True)

# ---- 业务模块 ----
# 使用列表而非 dict（key==value 无需 dict 映射）
_BUSINESS_MODULES = [
    'organization', 'policy', 'projects', 'school',
    # supported_village_export 必须先于 supported_village 注册：
    # 后者的 /{village_id} 动态路由会把 "export" 当 int 解析（422），
    # 静态导出路由需先匹配（FastAPI 按注册顺序匹配）
    'supported_village_export', 'supported_village',  # 帮扶村核心模块：CRUD+10板块年度数据+导入导出，已完整实现
    'rural_works', 'rural_tasks',
    'villages', 'village_templates', 'validation', 'report_templates', 'approval',
    'messages', 'feedback', 'todos', 'ai', 'map', 'project_milestones',
    'funds', 'fund_budgets', 'fund_lifecycle', 'work_logs', 'assessment',
    'system_health', 'performance', 'monitoring_legacy', 'data_quality',
    'ai_enhanced', 'data_sync', 'offline_map', 'batch_operations', 'sync',
    'user_permissions', 'machine_code', 'effectiveness', 'sentiment',
    'messages_extended', 'encryption', 'search', 'menus', 'permission_package',
    'org_module_policy', 'subordinate_registry', 'control_package',
    'subordinate_reports', 'files', 'permission_packs',
]

_loaded_count = 0
_failed_modules = []

for _route_name in _BUSINESS_MODULES:
    try:
        _mod = importlib.import_module(f'app.api.v1.{_route_name}')
        if hasattr(_mod, 'router'):
            api_v1_router.include_router(_mod.router)
            _loaded_count += 1
            logger.debug("已加载路由: %s", _route_name)
        else:
            logger.warning("模块 %s 中未找到 router 对象", _route_name)
            _failed_modules.append(_route_name)
    except Exception as e:
        _failed_modules.append(_route_name)
        logger.warning("加载 %s 路由失败: %s", _route_name, e, exc_info=True)

logger.info("路由加载完成: 成功 %d/%d 个", _loaded_count, len(_BUSINESS_MODULES))
if _failed_modules:
    logger.warning("以下路由模块加载失败: %s", ", ".join(_failed_modules))

__all__ = ["api_v1_router"]
