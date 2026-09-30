"""
监控数据模型
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import synonym

from app.models.base import Base


class APIMetric(Base):
    """API性能指标表"""

    __tablename__ = "api_metrics"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    response_time_ms = Column(Float, nullable=False)
    status_code = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    user_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


class AlertRule(Base):
    """告警规则表"""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # response_time/error_rate/resource
    threshold = Column(Float, nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=60)
    channels = Column(JSON, nullable=False)  # ["email", "webhook"]
    webhook_url = Column(String(500), nullable=True)
    email_recipients = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AlertHistory(Base):
    """告警历史表"""

    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(
        Integer,
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    # 消费端（api/v1/system/monitor.py）按 AlertHistory.created_at 排序/取值，
    # 而本表只有 triggered_at —— AttributeError 被上层 except 吞掉，告警历史
    # 恒为空列表（深审 LIVE）。以 synonym 暴露同名属性别名，读写与
    # order_by/列表达式语义与 triggered_at 完全一致，无需改表。
    created_at = synonym("triggered_at")
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(Text, nullable=False)
    metric_value = Column(Float, nullable=True)
    status = Column(String(20), default="triggered", nullable=False)  # triggered/resolved
