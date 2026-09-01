"""
API v1 路由模块
注册所有业务路由

全部使用静态导入（v1.11.3 事故修复）：
此前业务模块经 importlib.import_module(f'app.api.v1.{name}') 动态加载，
PyInstaller 静态分析无法跟踪 f-string 动态导入，冻结包内 47 个业务路由
全部缺失（Kylin 真机 403/接口全挂的根因）。静态导入 100% 被打包收集，
且任何路由模块损坏会在启动时快速失败，而非静默降级为残缺 API。
"""

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

# ==================== 子模块包 ====================
from app.api.v1.auth import router as auth_router  # noqa: E402
from app.api.v1.data import router as data_router  # noqa: E402
from app.api.v1.import_export import router as import_export_router  # noqa: E402
from app.api.v1.system import router as system_router  # noqa: E402
from app.api.v1.monitoring import (  # noqa: E402
    metrics as monitoring_metrics_module,
    secrets as monitoring_secrets_module,
    data_tier as monitoring_data_tier_module,
)
from app.api.v1.messages import notifications_router  # noqa: E402
from app.api.v1.reminders import router as reminders_router  # noqa: E402

# system 子模块（system/__init__ 已含这些路由；此处直挂保持 /api/v1/* 历史表面）
from app.api.v1.system import health as system_health_module  # noqa: E402
from app.api.v1.system import env as system_env_module  # noqa: E402
from app.api.v1.system import config_package as system_config_package_module  # noqa: E402

# ==================== 业务模块（静态导入，顺序敏感） ====================
# 注册顺序 = FastAPI 路由匹配优先级。supported_village_export 必须先于
# supported_village：后者的 /{village_id} 动态路由会把 "export" 当 int 解析（422）。
from app.api.v1 import (  # noqa: E402
    organization,
    policy,
    projects,
    school,
    supported_village_export,  # 必须先于 supported_village（见上）
    supported_village,
    rural_works,
    rural_tasks,
    villages,
    village_templates,
    validation,
    report_templates,
    approval,
    messages,
    feedback,
    todos,
    ai,
    map,
    project_milestones,
    funds,
    fund_budgets,
    fund_lifecycle,
    work_logs,
    assessment,
    system_health,
    performance,
    monitoring_legacy,
    data_quality,
    ai_enhanced,
    data_sync,
    offline_map,
    batch_operations,
    sync,
    user_permissions,
    machine_code,
    effectiveness,
    sentiment,
    encryption,
    search,
    menus,
    permission_package,
    org_module_policy,
    subordinate_registry,
    control_package,
    subordinate_reports,
    files,
    permission_packs,
)

# ==================== 按序注册 ====================
api_v1_router.include_router(auth_router)
logger.debug("已加载路由: auth")
api_v1_router.include_router(data_router)
logger.debug("已加载路由: data")
api_v1_router.include_router(import_export_router)
logger.debug("已加载路由: import_export")
api_v1_router.include_router(system_router)
logger.debug("已加载路由: system")

# system 子模块直挂（历史表面，勿删）
api_v1_router.include_router(system_health_module.router)
api_v1_router.include_router(system_env_module.router)
api_v1_router.include_router(system_config_package_module.router)

api_v1_router.include_router(monitoring_metrics_module.router)
api_v1_router.include_router(monitoring_secrets_module.router)
api_v1_router.include_router(monitoring_data_tier_module.router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(reminders_router)

# 业务模块：按上方静态导入顺序逐一注册
_BUSINESS_MODULES = [
    organization, policy, projects, school,
    supported_village_export, supported_village,
    rural_works, rural_tasks,
    villages, village_templates, validation, report_templates, approval,
    messages, feedback, todos, ai, map, project_milestones,
    funds, fund_budgets, fund_lifecycle, work_logs, assessment,
    system_health, performance, monitoring_legacy, data_quality,
    ai_enhanced, data_sync, offline_map, batch_operations, sync,
    user_permissions, machine_code, effectiveness, sentiment,
    encryption, search, menus, permission_package,
    org_module_policy, subordinate_registry, control_package,
    subordinate_reports, files, permission_packs,
]

for _mod in _BUSINESS_MODULES:
    api_v1_router.include_router(_mod.router)

logger.info(
    "路由加载完成: 静态注册 %d 个业务模块 + 子模块包（快速失败模式：任一模块损坏即启动中止）",
    len(_BUSINESS_MODULES),
)

__all__ = ["api_v1_router"]
