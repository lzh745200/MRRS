"""下级单位系统注册表模型

上级单位追踪和管理下级单位部署的单机系统实例。
通过注册上报包和管控配置包实现离线双向管理。
"""

from sqlalchemy import Column, Date, Integer, String, Text

from app.models.base import BaseModel, UtcDateTime


class SubordinateInstance(BaseModel):
    """下级单位系统实例注册表

    记录每个下级单位部署的单机系统实例信息，
    包括授权状态、版本、最后配置下发时间等。
    """

    __tablename__ = "subordinate_instances"

    organization_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="所属组织ID",
    )
    instance_code = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="下级系统唯一标识（首次初始化时生成）",
    )
    machine_code = Column(
        String(255),
        nullable=True,
        comment="绑定的机器码",
    )
    system_version = Column(
        String(32),
        nullable=True,
        comment="最后已知系统版本",
    )
    license_status = Column(
        String(20),
        default="pending",
        nullable=False,
        server_default="pending",
        comment="授权状态: pending-待授权, active-已授权, expired-已过期, revoked-已撤销",
    )
    license_expiry = Column(
        Date,
        nullable=True,
        comment="授权到期日",
    )
    last_config_hash = Column(
        String(64),
        nullable=True,
        comment="最后下发的管控配置包SHA256哈希",
    )
    last_config_applied_at = Column(
        UtcDateTime(),
        nullable=True,
        comment="下级最后应用配置的时间",
    )
    last_report_at = Column(
        UtcDateTime(),
        nullable=True,
        comment="最后收到状态报告的时间",
    )
    user_count = Column(
        Integer,
        default=0,
        comment="下级系统注册用户数",
    )
    status = Column(
        String(20),
        default="unknown",
        nullable=False,
        server_default="unknown",
        comment="在线状态: online-在线, offline-离线, unknown-未知",
    )
    remark = Column(
        Text,
        nullable=True,
        comment="备注",
    )
    created_by = Column(
        Integer,
        nullable=True,
        comment="注册操作人用户ID",
    )
