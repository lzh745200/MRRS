"""create user_sessions table

Revision ID: user_session_001
Revises: rbac_code_001
Create Date: 2026-10-14 13:50:00

新增"用户会话登记表"，让 `GET /system/admin/users/{id}/sessions` 与
`POST .../sessions/{id}/revoke` 从"恒返回空 / 无法精确吊销"变为真实可用：
登录时落一条（access/refresh 的 jti + IP/UA + 有效期），按会话吊销即把该 jti
写入黑名单（内存 + token_blacklist 表）。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "user_session_001"
down_revision = "rbac_code_001"
branch_labels = None
depends_on = None


def upgrade():
    """Create user_sessions table（幂等：已存在则跳过）."""
    insp = sa.inspect(op.get_bind())
    if insp.has_table("user_sessions"):
        return
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True, comment="主键ID"),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="所属用户ID",
        ),
        sa.Column("token_jti", sa.String(64), nullable=False, comment="访问令牌 jti（唯一）"),
        sa.Column("refresh_jti", sa.String(64), nullable=True, comment="刷新令牌 jti（一并吊销）"),
        sa.Column("ip_address", sa.String(64), nullable=True, comment="登录来源 IP"),
        sa.Column("user_agent", sa.String(512), nullable=True, comment="登录来源 User-Agent"),
        sa.Column("login_at", sa.DateTime(), nullable=False, comment="登录时间"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True, comment="最近刷新时间"),
        sa.Column("expires_at", sa.DateTime(), nullable=True, comment="刷新令牌过期时间"),
        sa.Column("revoked_at", sa.DateTime(), nullable=True, comment="吊销时间（空=活跃）"),
        sa.Column("revoked_by", sa.Integer(), nullable=True, comment="执行吊销的管理员ID"),
        sa.Column("revoke_reason", sa.String(100), nullable=True, comment="吊销原因"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_token_jti", "user_sessions", ["token_jti"], unique=True)


def downgrade():
    """Drop user_sessions table."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("user_sessions"):
        return
    op.drop_index("ix_user_sessions_token_jti", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
