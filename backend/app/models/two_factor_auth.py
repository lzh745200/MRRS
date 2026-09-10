"""
双因素认证模型
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import relationship

from app.models.base import Base


class TwoFactorAuth(Base):
    """双因素认证表"""

    __tablename__ = "two_factor_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    secret_key = Column(String(255), nullable=False)  # 加密存储
    # MutableList 包装是必需的，不是风格选择（2026-09-06）：
    # 裸 Column(JSON) 对"就地修改"（list.remove/append）不产生 attribute 事件，
    # SQLAlchemy 认为属性未变 → 不生成 UPDATE → 提交静默丢失。
    # 后果：verify_login 里 `backup_codes.remove(token)` 从未落库，备用恢复码可无限
    # 重复使用，"每个恢复码只能使用一次"的承诺被破坏，泄露一个码即永久绕过 2FA。
    backup_codes = Column(MutableList.as_mutable(JSON), nullable=True)  # 备用恢复码列表
    enabled = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    user = relationship("User", back_populates="two_factor_auth")


# 循环引用延迟注册：确保 User 在 mapper 配置前已定义（import 语句位于类定义之后）
from . import user  # noqa: F401,E402
