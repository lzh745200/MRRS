"""P3 到期任务：只停用过期且未改密的账号，幂等且吊销会话。"""
from datetime import timedelta

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.user import User
from app.services.user_service import expire_provisioned_credentials
from app.utils.time_utils import utcnow


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_expire_only_due_first_login_accounts(monkeypatch):
    db = _db()
    now = utcnow()
    due = User(username="due", hashed_password="x", must_change_password=True,
               credential_expires_at=now - timedelta(minutes=1), is_active=True)
    fresh = User(username="fresh", hashed_password="x", must_change_password=True,
                 credential_expires_at=now + timedelta(days=1), is_active=True)
    changed = User(username="changed", hashed_password="x", must_change_password=False,
                   credential_expires_at=now - timedelta(days=1), is_active=True)
    db.add_all([due, fresh, changed]); db.commit()

    count = expire_provisioned_credentials(db)
    assert count == 1
    db.refresh(due); db.refresh(fresh); db.refresh(changed)
    assert due.is_active is False and due.token_version == 1
    assert fresh.is_active is True
    assert changed.is_active is True
    assert expire_provisioned_credentials(db) == 0


def test_enforce_credential_not_expired_branches(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.core.security import enforce_credential_not_expired

    now = utcnow()
    # 非 datetime（测试替身/Mock）直接放行
    enforce_credential_not_expired(SimpleNamespace(credential_expires_at=None), now)
    enforce_credential_not_expired(SimpleNamespace(credential_expires_at=now + timedelta(days=1)), now)
    with pytest.raises(HTTPException):
        enforce_credential_not_expired(
            SimpleNamespace(id=1, username="u", credential_expires_at=now - timedelta(days=1)),
            now,
            SimpleNamespace(headers={}),
        )


def test_scheduler_job_runs_and_logs(monkeypatch):
    from app.services import backup_scheduler as bs

    class _S:
        def close(self):
            pass

    called = []
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: _S())
    monkeypatch.setattr(
        "app.services.user_service.expire_provisioned_credentials",
        lambda db: called.append(True) or 2,
    )
    bs.account_credential_expiry_job()
    assert called == [True]


def test_expire_none_db_and_scheduler_zero(monkeypatch):
    from app.services import backup_scheduler as bs
    from app.services.user_service import expire_provisioned_credentials

    assert expire_provisioned_credentials(None) == 0
    class _S:
        def close(self): pass
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: _S())
    monkeypatch.setattr("app.services.user_service.expire_provisioned_credentials", lambda db: 0)
    bs.account_credential_expiry_job()
