"""机器码模型

用于管理用户注册的机器码和通行码系统。
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, UtcDateTime

from .organization import Organization  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册


class MachineCode(Base):
    """机器码表

    存储机器码、通行码及其绑定关系。
    用于实现基于硬件的用户注册和登录控制。
    支持机器级别和组织级别的通行码管理。
    """

    __tablename__ = "machine_codes"

    id = Column(Integer, primary_key=True, index=True)
    machine_code = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="机器码（基于硬件信息生成）",
    )
    pass_code = Column(String(255), unique=True, index=True, nullable=False, comment="通行码（激活码）")
    status = Column(
        String(20),
        default="pending",
        index=True,
        comment="状态: pending-待使用, active-已激活, revoked-已撤销",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="绑定的用户ID",
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="关联的组织ID（用于组织通行码）",
    )
    allow_subordinate_generation = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否允许下级组织生成通行码",
    )
    restrict_permissions = Column(Text, default="", comment="此机器码限制的功能权限(JSON数组)")
    description = Column(Text, comment="备注说明")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID（管理员）")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="创建时间")
    activated_at = Column(UtcDateTime(), nullable=True, comment="激活时间")
    revoked_at = Column(UtcDateTime(), nullable=True, comment="撤销时间")
    updated_at = Column(UtcDateTime(), onupdate=func.now(), comment="更新时间")

    # 关系
    user = relationship("User", foreign_keys=[user_id], lazy="select")
    creator = relationship("User", foreign_keys=[created_by], lazy="select")
    organization = relationship("Organization", foreign_keys=[organization_id], lazy="select")

    def __repr__(self):
        code_preview = self.machine_code[:16]
        return f"<MachineCode(machine_code='{code_preview}...', " f"status='{self.status}', user_id={self.user_id})>"
