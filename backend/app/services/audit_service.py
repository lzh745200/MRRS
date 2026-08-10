import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.transaction import safe_commit
from app.models.audit import (
    APIAccessLog,
    AuditAction,
    AuditLevel,
    AuditLog,
    AuditStatus,
    DataExportLog,
    LoginAttempt,
    SecurityEvent,
)

logger = logging.getLogger(__name__)


class AuditContext:
    def __init__(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
    ):
        self.user_id = user_id
        self.username = username
        self.user_ip = user_ip
        self.user_agent = user_agent
        self.session_id = session_id
        self.trace_id = trace_id
        self.request_path = request_path
        self.request_method = request_method
        self.start_time = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "user_ip": self.user_ip,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "request_path": self.request_path,
            "request_method": self.request_method,
        }


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: AuditAction,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        context: Optional[AuditContext] = None,
        status: AuditStatus = AuditStatus.SUCCESS,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        error_message: Optional[str] = None,
        level: AuditLevel = AuditLevel.INFO,
        metadata: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        response_status: Optional[int] = None,
    ) -> AuditLog:
        audit = AuditLog(
            user_id=context.user_id if context else None,
            username=context.username if context else None,
            user_ip=context.user_ip if context else None,
            user_agent=context.user_agent if context else None,
            session_id=context.session_id if context else None,
            trace_id=context.trace_id if context else None,
            request_path=context.request_path if context else None,
            request_method=context.request_method if context else None,
            action=action.value if isinstance(action, AuditAction) else action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            old_value=old_value,
            new_value=new_value,
            status=status.value if isinstance(status, AuditStatus) else status,
            error_message=error_message,
            level=level.value if isinstance(level, AuditLevel) else level,
            metadata_=metadata,
            duration_ms=duration_ms,
            response_status=response_status,
        )

        self.db.add(audit)
        safe_commit(self.db)
        self.db.refresh(audit)

        logger.info(
            f"Audit: {action.value if isinstance(action, AuditAction) else action} on {resource_type}:{resource_id}"
        )
        return audit

    def log_create(
        self,
        resource_type: str,
        resource_id: Any,
        new_value: Dict,
        context: Optional[AuditContext] = None,
    ) -> AuditLog:
        return self.log(
            action=AuditAction.CREATE,
            resource_type=resource_type,
            resource_id=str(resource_id),
            context=context,
            new_value=new_value,
        )

    def log_update(
        self,
        resource_type: str,
        resource_id: Any,
        old_value: Dict,
        new_value: Dict,
        context: Optional[AuditContext] = None,
    ) -> AuditLog:
        return self.log(
            action=AuditAction.UPDATE,
            resource_type=resource_type,
            resource_id=str(resource_id),
            context=context,
            old_value=old_value,
            new_value=new_value,
        )

    def log_delete(
        self,
        resource_type: str,
        resource_id: Any,
        old_value: Dict,
        context: Optional[AuditContext] = None,
    ) -> AuditLog:
        return self.log(
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=str(resource_id),
            context=context,
            old_value=old_value,
        )

    def log_read(
        self,
        resource_type: str,
        resource_id: Optional[Any] = None,
        context: Optional[AuditContext] = None,
    ) -> AuditLog:
        return self.log(
            action=AuditAction.READ,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            context=context,
        )

    def log_login(
        self,
        username: str,
        success: bool,
        user_id: Optional[int] = None,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> AuditLog:
        context = AuditContext(user_id=user_id, username=username, user_ip=user_ip, user_agent=user_agent)

        login_attempt = LoginAttempt(
            username=username,
            ip_address=user_ip,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
        )
        self.db.add(login_attempt)

        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        level = AuditLevel.INFO if success else AuditLevel.WARNING

        return self.log(
            action=action,
            resource_type="authentication",
            resource_id=username,
            context=context,
            status=AuditStatus.SUCCESS if success else AuditStatus.FAILED,
            error_message=failure_reason,
            level=level,
        )

    def log_api_access(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_params: Optional[Dict] = None,
        response_status: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> APIAccessLog:
        access_log = APIAccessLog(
            user_id=user_id,
            username=username,
            endpoint=endpoint,
            method=method,
            request_params=request_params,
            ip_address=ip_address,
            user_agent=user_agent,
            response_status=response_status,
            response_time_ms=response_time_ms,
            session_id=session_id,
        )
        self.db.add(access_log)
        safe_commit(self.db)
        self.db.refresh(access_log)
        return access_log

    def log_export(
        self,
        user_id: int,
        username: Optional[str],
        export_type: str,
        data_types: List[str],
        file_format: str,
        record_count: Optional[int] = None,
        status: AuditStatus = AuditStatus.SUCCESS,
        error_message: Optional[str] = None,
    ) -> DataExportLog:
        export_log = DataExportLog(
            user_id=user_id,
            username=username,
            export_type=export_type,
            data_types=data_types,
            file_format=file_format,
            record_count=record_count,
            status=status.value if isinstance(status, AuditStatus) else status,
            error_message=error_message,
        )
        self.db.add(export_log)
        safe_commit(self.db)
        self.db.refresh(export_log)

        self.log(
            action=AuditAction.EXPORT,
            resource_type="data_export",
            resource_id=str(export_log.id),
            context=AuditContext(
                user_id=user_id,
                username=username,
                request_path=f"/export/{export_type}",
            ),
            new_value={
                "export_type": export_type,
                "data_types": data_types,
                "record_count": record_count,
            },
            status=status,
        )

        return export_log

    def query_audit_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[AuditStatus] = None,
        level: Optional[AuditLevel] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        query = self.db.query(AuditLog)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            action_value = action.value if isinstance(action, AuditAction) else action
            query = query.filter(AuditLog.action == action_value)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        if status:
            status_value = status.value if isinstance(status, AuditStatus) else status
            query = query.filter(AuditLog.status == status_value)
        if level:
            level_value = level.value if isinstance(level, AuditLevel) else level
            query = query.filter(AuditLog.level == level_value)

        total = query.count()
        logs = query.order_by(desc(AuditLog.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        return {
            "items": [log.to_dict() for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_audit_stats(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict:
        query = self.db.query(AuditLog)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        action_counts = dict(
            query.with_entities(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()
        )

        status_counts = dict(
            query.with_entities(AuditLog.status, func.count(AuditLog.id)).group_by(AuditLog.status).all()
        )

        level_counts = dict(query.with_entities(AuditLog.level, func.count(AuditLog.id)).group_by(AuditLog.level).all())

        top_users = dict(
            query.with_entities(AuditLog.username, func.count(AuditLog.id))
            .group_by(AuditLog.username)
            .order_by(func.count(AuditLog.id).desc())
            .limit(10)
            .all()
        )

        recent_activity = query.order_by(desc(AuditLog.created_at)).limit(20).all()

        # 前端统计卡派生字段（today_operations / active_users / failed_operations / warnings）
        from datetime import datetime as _dt

        today_start = _dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_operations = (
            self.db.query(func.count(AuditLog.id))
            .filter(AuditLog.created_at >= today_start)
            .scalar()
            or 0
        )
        active_users = len(top_users)
        failed_operations = sum(
            c for k, c in status_counts.items() if str(k).lower() in ("failed", "failure", "error")
        )
        warnings = sum(
            c for k, c in level_counts.items() if str(k).lower() in ("warning", "warn")
        )

        return {
            "total_count": query.count(),
            "by_action": action_counts,
            "by_status": status_counts,
            "by_level": level_counts,
            "top_users": top_users,
            "recent_activity": [log.to_dict() for log in recent_activity],
            # 前端兼容字段
            "today_operations": today_operations,
            "total_operations": query.count(),
            "active_users": active_users,
            "failed_operations": failed_operations,
            "warnings": warnings,
        }


class SecurityEventService:
    def __init__(self, db: Session):
        self.db = db

    def create_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        source_ip: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        details: Optional[Dict] = None,
        affected_resources: Optional[List[str]] = None,
    ) -> SecurityEvent:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            source_ip=source_ip,
            user_id=user_id,
            username=username,
            description=description,
            details=details,
            affected_resources=affected_resources,
        )
        self.db.add(event)
        safe_commit(self.db)
        self.db.refresh(event)

        logger.warning(f"Security event: {event_type} - {description}")
        return event

    def log_failed_login(self, username: str, ip_address: str, reason: str = "Invalid credentials") -> SecurityEvent:
        existing_attempts = (
            self.db.query(LoginAttempt)
            .filter(
                LoginAttempt.username == username,
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.attempt_time >= datetime.now() - timedelta(hours=1),
                LoginAttempt.success == False,  # noqa: E712
            )
            .count()
        )

        details = {"attempt_count": existing_attempts + 1, "reason": reason}

        if existing_attempts >= 5:
            severity = "high"
            event_type = "brute_force_attempt"
        elif existing_attempts >= 3:
            severity = "medium"
            event_type = "multiple_failed_logins"
        else:
            severity = "low"
            event_type = "failed_login"

        return self.create_event(
            event_type=event_type,
            severity=severity,
            description=f"Failed login attempt for user '{username}' from IP {ip_address}",
            source_ip=ip_address,
            username=username,
            details=details,
        )

    def resolve_event(self, event_id: int, resolved_by: int, resolution_notes: str) -> SecurityEvent:
        event = self.db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
        if event:
            event.resolved = True
            event.resolved_at = datetime.now()
            event.resolved_by = resolved_by
            event.resolution_notes = resolution_notes
            safe_commit(self.db)
            self.db.refresh(event)
        return event

    def get_events(
        self,
        severity: Optional[str] = None,
        event_type: Optional[str] = None,
        resolved: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        query = self.db.query(SecurityEvent)

        if severity:
            query = query.filter(SecurityEvent.severity == severity)
        if event_type:
            query = query.filter(SecurityEvent.event_type == event_type)
        if resolved is not None:
            query = query.filter(SecurityEvent.resolved == resolved)
        if start_date:
            query = query.filter(SecurityEvent.created_at >= start_date)
        if end_date:
            query = query.filter(SecurityEvent.created_at <= end_date)

        total = query.count()
        events = query.order_by(SecurityEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return {
            "items": [event.to_dict() for event in events],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_security_stats(self) -> Dict:
        severity_counts = dict(
            self.db.query(SecurityEvent.severity, func.count(SecurityEvent.id)).group_by(SecurityEvent.severity).all()
        )

        unresolved_by_severity = dict(
            self.db.query(SecurityEvent.severity, func.count(SecurityEvent.id))
            .filter(SecurityEvent.resolved == False)  # noqa: E712
            .group_by(SecurityEvent.severity)
            .all()
        )

        recent_events = self.db.query(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(10).all()

        return {
            "total_events": self.db.query(SecurityEvent).count(),
            "unresolved_count": self.db.query(SecurityEvent)
            .filter(SecurityEvent.resolved == False).count(),  # noqa: E712
            "by_severity": severity_counts,
            "unresolved_by_severity": unresolved_by_severity,
            "recent_events": [e.to_dict() for e in recent_events],
        }
