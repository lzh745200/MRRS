"""
审计日志工具

用于记录关键业务操作的审计日志，包括：
- 用户操作（登录、登出、权限变更）
- 数据修改（创建、更新、删除）
- 敏感操作（导出、备份、配置变更）

审计日志同时写入：
1. Python logging 系统（app.log 中的 [AUDIT] JSON 行）
2. 数据库 audit_logs / login_attempts 表（合规审计追踪）
"""

import json
import logging
from app.utils.time_utils import utcnow
from enum import Enum
from typing import Any, Dict, Optional
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


def _safe_json(payload: Dict[str, Any]) -> str:
    """审计数据 JSON 序列化（绝不抛异常）。

    details 里可能出现 datetime/Decimal/ORM 对象（log_data_change 传入
    old_data/new_data），default=str 兜住类型问题（深审 #81）；循环引用会让
    json.dumps 抛 ValueError，此时降级为最小可读摘要 —— 审计序列化失败
    绝不能冒泡进业务流。
    """
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as exc:
        logger.warning("审计数据序列化失败，降级为摘要: %s", exc)
        return json.dumps(
            {"action": str(payload.get("action")), "serialization_error": str(exc)},
            ensure_ascii=False,
        )


class AuditAction(str, Enum):
    """审计操作类型"""

    # 认证相关
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"

    # 数据操作
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    BATCH_DELETE = "batch_delete"

    # 敏感操作
    EXPORT = "export"
    IMPORT = "import"
    BACKUP = "backup"
    RESTORE = "restore"
    CONFIG_CHANGE = "config_change"

    # 权限操作
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ROLE_CHANGE = "role_change"


class AuditLevel(str, Enum):
    """审计级别"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditLogger:
    """审计日志记录器

    同时将审计事件写入 Python 日志和数据库，确保合规审计追踪完整。
    数据库写入使用独立 session，不影响调用方的事务。
    """

    @staticmethod
    def log(
        action: AuditAction,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        level: AuditLevel = AuditLevel.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        记录审计日志

        同时写入 Python 日志系统和数据库，确保审计追踪不丢失。

        Args:
            action: 操作类型
            user_id: 用户ID
            username: 用户名
            resource_type: 资源类型（如 "project", "fund", "village"）
            resource_id: 资源ID
            details: 详细信息（字典格式）
            level: 审计级别
            ip_address: IP地址
            user_agent: 用户代理
        """
        audit_data = {
            "timestamp": utcnow().isoformat(),
            "action": action.value if isinstance(action, AuditAction) else str(action),
            "user_id": user_id,
            "username": username,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "level": level.value if isinstance(level, AuditLevel) else str(level),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        # 1. 写入 Python 日志系统（app.log 中的 [AUDIT] JSON 行）
        log_message = f"[AUDIT] {_safe_json(audit_data)}"

        if level == AuditLevel.CRITICAL:
            logger.critical(log_message)
        elif level == AuditLevel.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # 2. 持久化到数据库（audit_logs / login_attempts 表）
        AuditLogger._persist_to_db(audit_data, action)

    @staticmethod
    def _persist_to_db(
        audit_data: Dict[str, Any],
        action: AuditAction,
    ) -> None:
        """将审计事件持久化到数据库。

        使用独立的 DB session，不影响调用方的事务。
        如果数据库写入失败，仅记录错误日志，不抛出异常（避免影响主业务流程）。

        Args:
            audit_data: 审计事件数据字典
            action: 审计操作类型
        """
        db = None
        try:
            from app.core.database import SessionLocal
            from app.models.audit import AuditLog as AuditLogModel, LoginAttempt

            db = SessionLocal()

            # 写入 audit_logs 表
            log_entry = AuditLogModel(
                user_id=audit_data.get("user_id") or None,
                username=audit_data.get("username"),
                user_ip=audit_data.get("ip_address"),
                user_agent=audit_data.get("user_agent"),
                action=audit_data.get("action", ""),
                resource_type=audit_data.get("resource_type"),
                resource_id=str(audit_data["resource_id"]) if audit_data.get("resource_id") else None,
                new_value=audit_data.get("details"),
                status="success",
                level=audit_data.get("level", "info"),
            )
            db.add(log_entry)

            # 登录相关事件同时写入 login_attempts 表
            if action in (AuditAction.LOGIN, AuditAction.LOGIN_FAILED):
                details = audit_data.get("details") or {}
                success = action == AuditAction.LOGIN
                login_attempt = LoginAttempt(
                    username=audit_data.get("username") or "",
                    ip_address=audit_data.get("ip_address"),
                    user_agent=audit_data.get("user_agent"),
                    success=success,
                    failure_reason=details.get("failure_reason"),
                )
                db.add(login_attempt)

            safe_commit(db)
        except Exception as exc:
            # 审计写入失败不应影响主业务流程，仅记录错误日志
            logger.error("审计日志持久化到数据库失败: %s", exc, exc_info=True)
            if db is not None:
                try:
                    db.rollback()
                except Exception as rb_err:
                    logger.warning("审计日志回滚失败: %s", rb_err)
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception as close_err:
                    logger.warning("审计日志关闭数据库连接失败: %s", close_err)

    @staticmethod
    def log_login(
        user_id: int,
        username: str,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        """记录登录操作"""
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        level = AuditLevel.INFO if success else AuditLevel.WARNING
        details = {"success": success}
        if failure_reason:
            details["failure_reason"] = failure_reason

        AuditLogger.log(
            action=action,
            user_id=user_id,
            username=username,
            details=details,
            level=level,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def log_data_change(
        action: AuditAction,
        user_id: int,
        username: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """记录数据变更操作"""
        details = {}
        if old_data:
            details["old_data"] = old_data
        if new_data:
            details["new_data"] = new_data

        AuditLogger.log(
            action=action,
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            level=AuditLevel.INFO,
            ip_address=ip_address,
        )

    @staticmethod
    def log_sensitive_operation(
        action: AuditAction,
        user_id: int,
        username: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """记录敏感操作"""
        AuditLogger.log(
            action=action,
            user_id=user_id,
            username=username,
            details=details,
            level=AuditLevel.CRITICAL,
            ip_address=ip_address,
        )

    @staticmethod
    def log_permission_change(
        action: AuditAction,
        operator_id: int,
        operator_name: str,
        target_user_id: int,
        target_username: str,
        permission_details: Dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> None:
        """记录权限变更操作"""
        details = {
            "target_user_id": target_user_id,
            "target_username": target_username,
            **permission_details,
        }

        AuditLogger.log(
            action=action,
            user_id=operator_id,
            username=operator_name,
            resource_type="user_permission",
            resource_id=target_user_id,
            details=details,
            level=AuditLevel.CRITICAL,
            ip_address=ip_address,
        )


# 便捷函数
def log_audit(
    action: AuditAction,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    **kwargs,
) -> None:
    """便捷的审计日志记录函数"""
    AuditLogger.log(action=action, user_id=user_id, username=username, **kwargs)
