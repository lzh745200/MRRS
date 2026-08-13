"""
审计增强服务
提供数据变更历史记录和对比功能
统一基于 AuditLog + AuditChange 实现字段级 Diff 留痕
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditLog, AuditStatus
from app.models.audit_change import AuditChange
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class AuditEnhancementService:
    """审计增强服务 — 为关键实体提供字段级变更 Diff 留痕"""

    @staticmethod
    def create_audit_log(
        db: Session,
        action: AuditAction,
        user: Any,
        resource_type: str,
        resource_id: str,
        detail: Optional[str] = None,
    ) -> AuditLog:
        """创建审计日志主记录"""
        log = AuditLog(
            user_id=getattr(user, "id", None),
            username=getattr(user, "username", None) or getattr(user, "full_name", None),
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            status=AuditStatus.SUCCESS.value,
            level="info",
            metadata_={"detail": detail} if detail else None,
        )
        db.add(log)
        # 显式提交——审计日志不应依赖调用方的事务提交，
        # 否则一旦调用方未 commit，审计轨迹会静默丢失
        safe_commit(db)
        return log

    @staticmethod
    def log_entity_changes(
        db: Session,
        action: AuditAction,
        user: Any,
        resource_type: str,
        resource_id: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
        key_fields: Optional[List[str]] = None,
        detail: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        一键记录实体变更：创建审计日志 + 记录字段级 Diff。
        返回创建的 AuditLog，如果没有有效变更则返回 None。
        """
        change_type = {
            AuditAction.CREATE: "create",
            AuditAction.UPDATE: "update",
            AuditAction.DELETE: "delete",
        }.get(action, action.value)

        audit_log = AuditEnhancementService.create_audit_log(
            db, action, user, resource_type, resource_id, detail=detail
        )
        AuditEnhancementService.record_changes(
            db, audit_log, old_data, new_data, change_type, key_fields
        )
        return audit_log

    @staticmethod
    def record_changes(
        db: Session,
        audit_log: AuditLog,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
        change_type: str = "update",
        key_fields: Optional[List[str]] = None,
    ):
        """
        记录数据变更详情

        Args:
            db: 数据库会话
            audit_log: 审计日志对象
            old_data: 旧数据
            new_data: 新数据
            change_type: 变更类型(create/update/delete)
            key_fields: 如果提供，只记录这些关键字段的变更；否则记录所有字段
        """
        if change_type == "create" and new_data:
            data = {k: v for k, v in new_data.items() if k not in ("id", "created_at", "updated_at")}
            if key_fields:
                data = {k: v for k, v in data.items() if k in key_fields}
            for field_name, new_value in data.items():
                change = AuditChange(
                    audit_log_id=audit_log.id,
                    field_name=field_name,
                    old_value=None,
                    new_value=AuditEnhancementService._serialize_value(new_value),
                    change_type="create",
                )
                db.add(change)

        elif change_type == "update" and old_data and new_data:
            data = {k: v for k, v in new_data.items() if k not in ("id", "created_at", "updated_at")}
            if key_fields:
                data = {k: v for k, v in data.items() if k in key_fields}
            for field_name, new_value in data.items():
                old_value = old_data.get(field_name)
                if old_value != new_value:
                    change = AuditChange(
                        audit_log_id=audit_log.id,
                        field_name=field_name,
                        old_value=AuditEnhancementService._serialize_value(old_value),
                        new_value=AuditEnhancementService._serialize_value(new_value),
                        change_type="update",
                    )
                    db.add(change)

        elif change_type == "delete" and old_data:
            data = {k: v for k, v in old_data.items() if k not in ("id", "created_at", "updated_at")}
            if key_fields:
                data = {k: v for k, v in data.items() if k in key_fields}
            for field_name, old_value in data.items():
                change = AuditChange(
                    audit_log_id=audit_log.id,
                    field_name=field_name,
                    old_value=AuditEnhancementService._serialize_value(old_value),
                    new_value=None,
                    change_type="delete",
                )
                db.add(change)

        # 显式提交——与 create_audit_log 一致：调用方可能在业务 commit 之后
        # 才记录变更（如 supported_village.py），不提交则字段级明细静默丢失。
        safe_commit(db)

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """序列化值为 JSON 兼容格式"""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (list, dict)):
            return value
        return str(value)

    @staticmethod
    def get_change_history(
        db: Session,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取实体的变更历史

        Returns:
            变更历史列表，按时间倒序
        """
        audit_logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

        if not audit_logs:
            return []

        log_ids = [log.id for log in audit_logs]
        all_changes = db.query(AuditChange).filter(AuditChange.audit_log_id.in_(log_ids)).all()
        changes_by_log: Dict[int, List[AuditChange]] = {}
        for change in all_changes:
            changes_by_log.setdefault(change.audit_log_id, []).append(change)

        history = []
        for log in audit_logs:
            changes = changes_by_log.get(log.id, [])
            history.append(
                {
                    "timestamp": (log.created_at.isoformat() if log.created_at else None),
                    "user_id": log.user_id,
                    "username": log.username,
                    "action": log.action,
                    "changes": [
                        {
                            "field": change.field_name,
                            "old_value": change.old_value,
                            "new_value": change.new_value,
                            "change_type": change.change_type,
                        }
                        for change in changes
                    ],
                }
            )

        return history
