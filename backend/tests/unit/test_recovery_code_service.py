"""P1：机器码一次性恢复码服务回归。"""

from datetime import timedelta

import pytest

from app.models.machine_recovery_code import MachineRecoveryCode
from app.services.recovery_code_service import (
    PURPOSE_ADMIN_RECOVERY,
    PURPOSE_PASSWORD_RESET,
    RecoveryCodeService,
)
from app.utils.time_utils import utcnow


def test_issue_check_consume_once(real_db_session):
    db = real_db_session
    code, expires_at = RecoveryCodeService.issue(db, "MC-1", PURPOSE_PASSWORD_RESET)
    assert len(code) == 8 and code.isdigit()
    assert expires_at > utcnow()

    assert RecoveryCodeService.check(db, "MC-1", code, PURPOSE_PASSWORD_RESET, consume=False)
    assert RecoveryCodeService.check(db, "MC-1", code, PURPOSE_PASSWORD_RESET, consume=True)
    # 第二次消费必须失败
    assert not RecoveryCodeService.check(db, "MC-1", code, PURPOSE_PASSWORD_RESET, consume=True)


def test_new_code_invalidates_old_code(real_db_session):
    db = real_db_session
    old, _ = RecoveryCodeService.issue(db, "MC-2")
    new, _ = RecoveryCodeService.issue(db, "MC-2")
    assert not RecoveryCodeService.check(db, "MC-2", old, PURPOSE_PASSWORD_RESET, consume=True)
    assert RecoveryCodeService.check(db, "MC-2", new, PURPOSE_PASSWORD_RESET, consume=True)


def test_expired_code_rejected(real_db_session):
    db = real_db_session
    code, _ = RecoveryCodeService.issue(db, "MC-3")
    db.query(MachineRecoveryCode).filter(
        MachineRecoveryCode.machine_code == "MC-3"
    ).update({"expires_at": utcnow() - timedelta(seconds=1)})
    db.commit()
    assert not RecoveryCodeService.check(db, "MC-3", code, PURPOSE_PASSWORD_RESET, consume=True)


def test_five_wrong_attempts_invalidate(real_db_session):
    db = real_db_session
    code, _ = RecoveryCodeService.issue(db, "MC-4")
    for _ in range(5):
        assert not RecoveryCodeService.check(
            db, "MC-4", "00000000", PURPOSE_PASSWORD_RESET, consume=True
        )
    assert not RecoveryCodeService.check(db, "MC-4", code, PURPOSE_PASSWORD_RESET, consume=True)


def test_purpose_isolation(real_db_session):
    db = real_db_session
    code, _ = RecoveryCodeService.issue(db, "MC-5", PURPOSE_ADMIN_RECOVERY)
    assert not RecoveryCodeService.check(
        db, "MC-5", code, PURPOSE_PASSWORD_RESET, consume=True
    )
    assert RecoveryCodeService.check(
        db, "MC-5", code, PURPOSE_ADMIN_RECOVERY, consume=True
    )


def test_invalid_purpose_rejected(real_db_session):
    with pytest.raises(ValueError):
        RecoveryCodeService.issue(real_db_session, "MC-6", "unknown")
