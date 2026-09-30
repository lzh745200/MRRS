import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.models.base import Base


class AuditAction(str, enum.Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"  # nosec B105
    PERMISSION_CHANGE = "permission_change"
    EXPORT = "export"
    IMPORT = "import"
    API_CALL = "api_call"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    CONFIG_CHANGE = "config_change"
    BACKUP = "backup"
    RESTORE = "restore"


class AuditLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_timestamp", "created_at"),
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(100), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)

    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True)

    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    status = Column(String(20), default=AuditStatus.SUCCESS.value)
    error_message = Column(Text, nullable=True)

    level = Column(String(20), default=AuditLevel.INFO.value)

    request_path = Column(String(500), nullable=True)
    request_method = Column(String(10), nullable=True)
    response_status = Column(Integer, nullable=True)

    duration_ms = Column(Integer, nullable=True)

    metadata_ = Column("metadata", JSON, nullable=True)

    session_id = Column(String(100), nullable=True, index=True)
    trace_id = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)

    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)

    source_ip = Column(String(45), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(100), nullable=True)

    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)

    affected_resources = Column(JSON, nullable=True)

    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_security_severity", "severity", "created_at"),
        Index("idx_security_type", "event_type", "created_at"),
    )


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)

    success = Column(Boolean, default=False)
    failure_reason = Column(String(200), nullable=True)

    attempt_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_login_attempts_user", "username", "attempt_time"),
        Index("idx_login_attempts_ip", "ip_address", "attempt_time"),
    )


class APIAccessLog(Base):
    __tablename__ = "api_access_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(100), nullable=True)

    endpoint = Column(String(500), nullable=False, index=True)
    method = Column(String(10), nullable=False)

    request_params = Column(JSON, nullable=True)
    request_body = Column(JSON, nullable=True)

    response_status = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    session_id = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_api_access_user", "user_id", "created_at"),
        Index("idx_api_access_endpoint", "endpoint", "created_at"),
    )


class DataExportLog(Base):
    __tablename__ = "data_export_logs"

    id = Column(Integer, primary_key=True, index=True)

    # 用户删除后置空 user_id（审计留痕保留）——SET NULL 要求列可空，历史快照里
    # 该列曾是 nullable=False，导致删用户必然 IntegrityError。
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(100), nullable=True)

    export_type = Column(String(50), nullable=False)
    data_types = Column(JSON, nullable=True)
    filters = Column(JSON, nullable=True)

    file_format = Column(String(20), nullable=True)
    record_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    file_path = Column(String(500), nullable=True)

    status = Column(String(20), default=AuditStatus.SUCCESS.value)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_export_user", "user_id", "created_at"),
        Index("idx_export_type", "export_type", "created_at"),
    )
