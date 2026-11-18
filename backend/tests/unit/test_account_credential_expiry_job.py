"""P3 到期任务：只停用过期且未改密的账号，幂等且吊销会话。"""
from datetime import timedelta

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
