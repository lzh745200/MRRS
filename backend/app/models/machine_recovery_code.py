"""机器码一次性恢复码模型。"""

from datetime import datetime, timezone

from sqlalchemy import Column, Index, Integer, String

from app.models.base import Base, UtcDateTime


class MachineRecoveryCode(Base):
    """本机密码重置/管理员恢复的一次性短时凭证。"""

    __tablename__ = "machine_recovery_codes"

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    machine_code = Column(String(64), nullable=False, index=True, comment="机器码")
    code_hash = Column(String(128), nullable=False, comment="恢复码 bcrypt/Argon2 哈希")
    purpose = Column(String(20), nullable=False, default="password_reset", comment="用途")
    expires_at = Column(UtcDateTime(), nullable=False, index=True, comment="过期时间")
    used_at = Column(UtcDateTime(), nullable=True, comment="消费时间")
    attempts = Column(Integer, nullable=False, default=0, comment="失败次数")
    created_at = Column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="签发时间",
    )

    __table_args__ = (
        Index(
            "ix_machine_recovery_lookup",
            "machine_code",
            "purpose",
            "used_at",
            "expires_at",
        ),
    )
