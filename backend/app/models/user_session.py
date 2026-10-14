"""用户会话登记表。

背景（2026-10-14）：系统此前**没有任何会话表**，`GET /system/admin/users/{id}/sessions`
只能返回 `sessions: []`（`token_blacklist` 只记录"已吊销的 jti"，无法反推活跃会话），
以至于会话区与"强制登出"功能不可达。

本表在**登录成功时**落一条记录（访问令牌 jti + 刷新令牌 jti + 来源 IP/UA + 有效期），
使"活跃会话列表"与"按会话精确吊销"成为可能：
- 列表：`revoked_at IS NULL AND expires_at > now`
- 吊销：把该会话的 jti 写入内存黑名单（`core.token_blacklist.add`，`validate_token` 会拦截）
  + 持久化到 `token_blacklist` 表（重启后仍生效）

多端登录语义：**允许**（同一用户可有多条活跃会话），按会话吊销只影响该条；
需要"一键踢掉全部设备"时仍走既有的 `token_version` 递增路径。

保留期：行不随令牌过期删除（留作审计），列表按 `expires_at` 过滤；
过期/已吊销行由清理作业按需回收。
"""
from sqlalchemy import Column, ForeignKey, Index, Integer, String

from .base import Base, UtcDateTime


class UserSession(Base):
    """一条登录会话（对应一对 access/refresh 令牌）。"""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_token_jti", "token_jti", unique=True),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户ID",
    )
    token_jti = Column(String(64), nullable=False, comment="访问令牌 jti（唯一）")
    refresh_jti = Column(String(64), nullable=True, comment="刷新令牌 jti（一并吊销）")
    ip_address = Column(String(64), nullable=True, comment="登录来源 IP")
    user_agent = Column(String(512), nullable=True, comment="登录来源 User-Agent")
    login_at = Column(UtcDateTime(), nullable=False, comment="登录时间")
    last_seen_at = Column(UtcDateTime(), nullable=True, comment="最近刷新时间")
    expires_at = Column(UtcDateTime(), nullable=True, comment="刷新令牌过期时间")
    revoked_at = Column(UtcDateTime(), nullable=True, comment="吊销时间（空=活跃）")
    revoked_by = Column(Integer, nullable=True, comment="执行吊销的管理员ID")
    revoke_reason = Column(String(100), nullable=True, comment="吊销原因")

    @property
    def is_active(self) -> bool:
        """未吊销即视为活跃（有效期由查询侧按 expires_at 过滤）。"""
        return self.revoked_at is None

    def to_dict(self) -> dict:
        """序列化。

        `session_id`/`created_at` 是前端会话面板的既有字段名
        （UserManagement.vue 的表格列与吊销调用都按它们取值），此处保持契约兼容；
        `login_at` 为本模型的规范字段名。
        """
        return {
            "id": self.id,
            "session_id": self.id,
            "created_at": self.login_at.isoformat() if self.login_at else None,
            "user_id": self.user_id,
            "jti": self.token_jti,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "login_at": self.login_at.isoformat() if self.login_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }
