"""
系统管理路由模块
整合所有子模块路由，提供统一的系统管理API入口

包含模块：
- admin: 系统管理员专用API（备份恢复、系统配置、日志管理等）
- audit: 审计日志API
- backup: 备份API
- cache: 缓存管理API
- config_package: 配置包管理API
- env: 运行环境检查API
- error_report: 错误报告API
- health: 系统健康检查API
- help: 帮助信息API
- init: 系统初始化API
- metrics: 系统指标API
- monitor: 系统监控API
- system: 核心系统API
- system_config: 系统配置API
- tasks: 后台任务API
- update_logs: 更新日志API
- zero_trust: 零信任安全API
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# 创建系统管理主路由
router = APIRouter(prefix="/system", tags=["系统管理"])

# ==================== 显式导入并注册所有子模块路由 ====================

# ---- 系统管理员 ----
try:
    from app.api.v1.system.admin import router as admin_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.admin 路由失败: {exc}") from exc
router.include_router(admin_router)
logger.debug("已加载路由: system.admin")

# ---- 审计日志 ----
try:
    from app.api.v1.system.audit import router as audit_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.audit 路由失败: {exc}") from exc
router.include_router(audit_router)
logger.debug("已加载路由: system.audit")

# ---- 备份管理 ----
try:
    from app.api.v1.system.backup import router as backup_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.backup 路由失败: {exc}") from exc
router.include_router(backup_router)
logger.debug("已加载路由: system.backup")

# ---- 缓存管理 ----
try:
    from app.api.v1.system.cache import router as cache_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.cache 路由失败: {exc}") from exc
router.include_router(cache_router)
logger.debug("已加载路由: system.cache")

# ---- 配置包管理 ----
try:
    from app.api.v1.system.config_package import router as config_package_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.config_package 路由失败: {exc}") from exc
router.include_router(config_package_router)
logger.debug("已加载路由: system.config_package")

# ---- 运行环境检查 ----
try:
    from app.api.v1.system.env import router as env_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.env 路由失败: {exc}") from exc
router.include_router(env_router)
logger.debug("已加载路由: system.env")

# ---- 错误报告 ----
try:
    from app.api.v1.system.error_report import router as error_report_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.error_report 路由失败: {exc}") from exc
router.include_router(error_report_router)
logger.debug("已加载路由: system.error_report")

# ---- 诊断包（P0-7，2026-10-17：现场排障一次性带全证据）----
try:
    from app.api.v1.system.diagnostics import router as diagnostics_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast（诊断包缺失会让现场排障回到
    # "隔电话挨个问"的状态，静默缺路由不可接受）。
    raise RuntimeError(f"加载 system.diagnostics 路由失败: {exc}") from exc
router.include_router(diagnostics_router)
logger.debug("已加载路由: system.diagnostics")

# ---- 业务数据体检（W17-008）----
try:
    from app.api.v1.system.business_health import router as business_health_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast（业务数据体检缺失会让管理员
    # 无法发现"村年度缺失/金额矛盾"这类数据质量问题，静默缺路由不可接受）。
    raise RuntimeError(f"加载 system.business_health 路由失败: {exc}") from exc
router.include_router(business_health_router)
logger.debug("已加载路由: system.business_health")

# ---- 系统自检（P3）----
try:
    from app.api.v1.system.self_check import router as self_check_router
except Exception as exc:
    raise RuntimeError(f"加载 system.self_check 路由失败: {exc}") from exc
router.include_router(self_check_router)
logger.debug("已加载路由: system.self_check")

# ---- 系统健康检查 ----
try:
    from app.api.v1.system.health import router as health_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.health 路由失败: {exc}") from exc
router.include_router(health_router)
logger.debug("已加载路由: system.health")

# ---- 帮助信息 ----
try:
    from app.api.v1.system.help import router as help_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.help 路由失败: {exc}") from exc
router.include_router(help_router)
logger.debug("已加载路由: system.help")

# ---- 国际化 ---- 已于 v1.15.16 随需求下线（后端 API 与前端页面一并移除；
# 系统为纯中文单语部署，多语言能力从未上线使用）

# ---- 系统初始化 ----
try:
    from app.api.v1.system.init import router as init_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.init 路由失败: {exc}") from exc
router.include_router(init_router)
logger.debug("已加载路由: system.init")

# ---- 系统指标 ----
try:
    from app.api.v1.system.metrics import router as metrics_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.metrics 路由失败: {exc}") from exc
router.include_router(metrics_router)
logger.debug("已加载路由: system.metrics")

# ---- 系统监控 ----
try:
    from app.api.v1.system.monitor import router as monitor_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.monitor 路由失败: {exc}") from exc
router.include_router(monitor_router)
logger.debug("已加载路由: system.monitor")

# ---- PII 密钥管理（R34-2：多机同步密钥漂移的自助修复入口）----
try:
    from app.api.v1.system.pii_key import router as pii_key_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.pii_key 路由失败: {exc}") from exc
router.include_router(pii_key_router)
logger.debug("已加载路由: system.pii_key")

# ---- 核心系统 ----
try:
    from app.api.v1.system.system import router as system_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.system 路由失败: {exc}") from exc
router.include_router(system_router)
logger.debug("已加载路由: system.system")

# ---- 系统配置 ----
try:
    from app.api.v1.system.system_config import router as system_config_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.system_config 路由失败: {exc}") from exc
router.include_router(system_config_router)
logger.debug("已加载路由: system.system_config")

# ---- 后台任务 ----
try:
    from app.api.v1.system.tasks import router as tasks_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.tasks 路由失败: {exc}") from exc
router.include_router(tasks_router)
logger.debug("已加载路由: system.tasks")

# ---- 更新日志 ----
try:
    from app.api.v1.system.update_logs import router as update_logs_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.update_logs 路由失败: {exc}") from exc
router.include_router(update_logs_router)
logger.debug("已加载路由: system.update_logs")

# ---- 零信任安全 ----
try:
    from app.api.v1.system.zero_trust import router as zero_trust_router
except Exception as exc:
    # 深审 #78：子模块导入失败必须 fail-fast —— 原实现只记 warning，端点会
    # 静默缺失（审计/零信任/备份这类安全路由缺失时无人察觉），且丢掉原始栈。
    raise RuntimeError(f"加载 system.zero_trust 路由失败: {exc}") from exc
router.include_router(zero_trust_router)
logger.debug("已加载路由: system.zero_trust")

__all__ = ["router"]
