"""
Token 黑名单数据模型
用于持久化被撤销的 Token
"""

from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, String

from app.models.base import Base, UtcDateTime


class TokenBlacklist(Base):
    """Token 黑名单模型"""

    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    token_jti = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="JWT ID (jti claim)",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="用户ID",
    )
    blacklisted_at = Column(
        UtcDateTime(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="加入黑名单时间",
    )
    expires_at = Column(
        UtcDateTime(),
        nullable=True,
        index=True,
        comment="Token 原始过期时间",
    )
    reason = Column(
        String(100),
        nullable=True,
        comment="加入黑名单原因: logout, password_change, revoked, expired",
    )

    # 复合索引
    __table_args__ = (
        Index("idx_token_blacklist_user_time", "user_id", "blacklisted_at"),
        Index("idx_token_blacklist_expires", "expires_at"),
        {"comment": "Token 黑名单表"},
    )

    def __repr__(self):
        return f"<TokenBlacklist(jti={self.token_jti}, user_id={self.user_id}, reason={self.reason})>"
