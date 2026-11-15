"""机器码一次性恢复码服务。"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.core.transaction import safe_commit
from app.models.machine_recovery_code import MachineRecoveryCode
from app.utils.time_utils import utcnow

PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_ADMIN_RECOVERY = "admin_recovery"
_ALLOWED_PURPOSES = {PURPOSE_PASSWORD_RESET, PURPOSE_ADMIN_RECOVERY}
_MAX_ATTEMPTS = 5
_DEFAULT_TTL_SECONDS = 600


class RecoveryCodeService:
    """签发/校验/消费本机一次性恢复码。

    只存 bcrypt 哈希；明文只在签发响应中出现一次。
    """

    @staticmethod
    def issue(
        db: Session,
        machine_code: str,
        purpose: str = PURPOSE_PASSWORD_RESET,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> Tuple[str, object]:
        if purpose not in _ALLOWED_PURPOSES:
            raise ValueError("invalid recovery purpose")
        now = utcnow()
        # 同一机器同一用途只保留一个有效码，旧码立即作废。
        db.query(MachineRecoveryCode).filter(
            MachineRecoveryCode.machine_code == machine_code,
            MachineRecoveryCode.purpose == purpose,
            MachineRecoveryCode.used_at.is_(None),
        ).update({MachineRecoveryCode.used_at: now}, synchronize_session=False)

        code = f"{secrets.randbelow(10 ** 8):08d}"
        expires_at = now + timedelta(seconds=max(60, min(int(ttl_seconds), 1800)))
        db.add(
            MachineRecoveryCode(
                machine_code=machine_code,
                code_hash=get_password_hash(code),
                purpose=purpose,
                expires_at=expires_at,
            )
        )
        safe_commit(db)
        return code, expires_at

    @staticmethod
    def _active_code(db: Session, machine_code: str, purpose: str) -> Optional[MachineRecoveryCode]:
        return (
            db.query(MachineRecoveryCode)
            .filter(
                MachineRecoveryCode.machine_code == machine_code,
                MachineRecoveryCode.purpose == purpose,
                MachineRecoveryCode.used_at.is_(None),
                MachineRecoveryCode.expires_at > utcnow(),
            )
            .order_by(MachineRecoveryCode.created_at.desc())
            .first()
        )

    @staticmethod
    def check(
        db: Session,
        machine_code: str,
        code: str,
        purpose: str,
        *,
        consume: bool,
    ) -> bool:
        if purpose not in _ALLOWED_PURPOSES:
            return False
        row = RecoveryCodeService._active_code(db, machine_code, purpose)
        if row is None:
            return False
        if not isinstance(getattr(row, "code_hash", None), str) or not row.code_hash:
            return False
        if not verify_password(code, row.code_hash or ""):
            row.attempts = (row.attempts or 0) + 1
            if row.attempts >= _MAX_ATTEMPTS:
                row.used_at = utcnow()
            safe_commit(db)
            return False
        if not consume:
            return True
        # 原子消费：并发两次重置只有一次能把 used_at 从 NULL 改为时间。
        updated = (
            db.query(MachineRecoveryCode)
            .filter(
                MachineRecoveryCode.id == row.id,
                MachineRecoveryCode.used_at.is_(None),
                MachineRecoveryCode.expires_at > utcnow(),
            )
            .update({MachineRecoveryCode.used_at: utcnow()}, synchronize_session=False)
        )
        safe_commit(db)
        return updated == 1
