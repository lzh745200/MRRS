"""账号开通包：源机导出记录 + 目标机一次性回执 + 失败尝试台账。

回执的 ``package_id`` **单独唯一**：机器码会随重装变化，不能并入唯一键，
否则同一包换机即可重放。

``AccountPackageAttempt`` 是 P4 限流台账：回执只在**成功导入后**才存在，
失败尝试无处落账；导入时也没有用户对象可复用登录锁定列，故按
``subject_key``（``export:<签发人id>`` / ``import:<目标机机器码>``）独立计数。
"""

from sqlalchemy import JSON, Column, Integer, String, Text
from sqlalchemy import func

from app.models.base import BaseModel, UtcDateTime


class AccountPackageExport(BaseModel):
    __tablename__ = "account_package_exports"

    package_id = Column(String(64), unique=True, nullable=False, index=True)
    format_version = Column(Integer, nullable=False, default=1, server_default="1")
    issuer_org_code = Column(String(32), nullable=False, index=True)
    issuer_user_id = Column(Integer, nullable=True)
    target_org_code = Column(String(32), nullable=False, index=True)
    binding_mode = Column(String(16), nullable=False, default="machine")
    target_machine_code = Column(String(64), nullable=True)
    kdf_iterations = Column(Integer, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    key_id = Column(String(64), nullable=True)
    issued_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    not_before = Column(UtcDateTime(), nullable=True)
    expires_at = Column(UtcDateTime(), nullable=False)
    state = Column(String(16), nullable=False, default="active", server_default="active", index=True)
    revoked_at = Column(UtcDateTime(), nullable=True)
    revoke_reason = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)


class AccountPackageReceipt(BaseModel):
    __tablename__ = "account_package_receipts"

    package_id = Column(String(64), unique=True, nullable=False, index=True)
    machine_code = Column(String(64), nullable=True, index=True, comment="仅审计，不参与唯一键")
    issuer_org_code = Column(String(32), nullable=True)
    target_org_code = Column(String(32), nullable=True, index=True)
    activated_org_id = Column(Integer, nullable=True)
    activated_user_id = Column(Integer, nullable=True)
    confirmed_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    state = Column(String(16), nullable=False, default="used", server_default="used")
    fail_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(String(64), nullable=True)


class AccountPackageAttempt(BaseModel):
    """P4 失败尝试台账：按作用域计数，达阈值临时锁定。"""

    __tablename__ = "account_package_attempts"

    subject_key = Column(String(160), unique=True, nullable=False, index=True)
    fail_count = Column(Integer, nullable=False, default=0, server_default="0")
    locked_until = Column(UtcDateTime(), nullable=True)
    last_error = Column(String(64), nullable=True)
    last_attempt_at = Column(UtcDateTime(), nullable=True)
