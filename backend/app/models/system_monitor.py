"""
系统监控模型
"""

from sqlalchemy import Column, Float, Index, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base, UtcDateTime


class SystemMonitor(Base):
    """系统监控模型"""

    __tablename__ = "system_monitors"

    __table_args__ = (
        Index("ix_system_monitors_created_at", "created_at"),
        Index("ix_system_monitors_host", "host"),
        Index("ix_system_monitors_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 系统指标
    cpu_usage = Column(Float, comment="CPU使用率")
    memory_usage = Column(Float, comment="内存使用率")
    disk_usage = Column(Float, comment="磁盘使用率")

    # 网络指标
    network_in = Column(Float, comment="网络入流量")
    network_out = Column(Float, comment="网络出流量")

    # 应用指标
    active_users = Column(Integer, comment="活跃用户数")
    request_count = Column(Integer, comment="请求数")
    error_count = Column(Integer, comment="错误数")

    # 数据库指标
    db_connections = Column(Integer, comment="数据库连接数")
    db_query_time = Column(Float, comment="数据库查询平均时间")

    # 元数据
    host = Column(String(100), comment="主机名")
    status = Column(String(50), comment="状态")
    notes = Column(Text, comment="备注")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="记录时间")

    def __repr__(self):
        return f"<SystemMonitor(id={self.id}, host='{self.host}', cpu={self.cpu_usage}%)>"
