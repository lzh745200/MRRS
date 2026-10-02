"""仪表盘相关数据模型"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.sql import func

from .base import Base, UtcDateTime


class DashboardActivity(Base):
    """自定义近期动态模型（前端手动添加的动态）"""

    __tablename__ = "dashboard_activities"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), default="project", comment="动态类型")
    action = Column(String(100), nullable=False, comment="操作")
    target = Column(String(500), nullable=False, comment="目标")
    user = Column(String(100), default="系统", comment="操作人")
    created_at = Column(UtcDateTime(), default=func.now())


class HiddenDashboardActivity(Base):
    """记录用户已隐藏（删除）的系统自动生成动态 ID

    系统动态（project_123, fund_456 等）来源于业务表动态查询，
    无法从数据库真正删除。通过此表持久化 "隐藏" 状态，
    确保刷新页面后已删除的动态不会重新出现。
    """

    __tablename__ = "hidden_dashboard_activities"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        String(200),
        nullable=False,
        unique=True,
        comment="被隐藏的动态ID，如 project_123",
    )
    hidden_at = Column(UtcDateTime(), default=func.now())
