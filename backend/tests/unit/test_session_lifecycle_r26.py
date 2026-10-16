"""用户会话登记与按会话吊销的回归用例（2026-10-14 R26）。

背景：系统此前没有会话表，`GET /system/admin/users/{id}/sessions` 恒返回 `sessions: []`，
会话区与"强制登出"不可达。本组用例锁定修复后的行为：

1. 登录成功 → 落一条会话（access/refresh 的 jti + IP/UA + 有效期）
2. 列表 → 只返回"未吊销且未过期"的会话
3. 按会话吊销 → 标记 revoked_at + 把 access/refresh 两个 jti 写入黑名单
   （`validate_token` 拦截黑名单 jti，因此吊销即时生效）
4. 令牌刷新 → 会话行指向新 jti（否则吊销会落到已废弃的旧 jti 上，表面成功实际失效）
5. 兼容旧语义：session_id 未命中会话表时，管理端退回 token_version 全量踢下线
"""
import asyncio
import contextlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.user import User
from app.models.user_session import UserSession
from app.services import session_service as svc
from app.utils.time_utils import utcnow


@pytest.fixture()
def db():
    """独立内存库：真实建表，覆盖模型约束与查询语义。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user(db):
    u = User(username="op1", hashed_password="x", role="user", is_active=True)
    db.add(u)
    db.commit()
    return u


def _fake_request(ip="10.1.2.3", ua="Mozilla/5.0 TestUA"):
    headers = {"user-agent": ua}
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers=headers)


def test_record_login_creates_session(db, user, monkeypatch):
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1", "sub": "op1"}
        if not token.startswith("refresh:")
        else {"jti": "ref-1", "sub": "op1"},
    )
    s = svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"},
                                 _fake_request())
    assert s is not None and s.id is not None
    assert s.token_jti == "acc-1" and s.refresh_jti == "ref-1"
    assert s.ip_address == "10.1.2.3" and s.user_agent == "Mozilla/5.0 TestUA"
    assert s.revoked_at is None and s.is_active


def test_record_login_failure_never_blocks_login(db, user, monkeypatch):
    """登记是旁路：令牌解析失败/写库异常都不得抛出（否则登录被审计表拖死）。"""
    monkeypatch.setattr(svc, "_decode", lambda token: {})
    assert svc.record_login_session(db, user, {"access_token": "x"}) is None


def test_list_active_sessions_filters_revoked_and_expired(db, user, monkeypatch):
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1"} if not token.startswith("refresh:") else {"jti": "ref-1"},
    )
    svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})

    active = svc.list_active_sessions(db, user.id)
    assert len(active) == 1

    # 吊销后不再出现在活跃列表
    svc.revoke_session(db, active[0], operator_id=99, reason="test")
    assert svc.list_active_sessions(db, user.id) == []

    # 已过期的会话同样不算活跃
    expired = UserSession(
        user_id=user.id,
        token_jti="acc-expired",
        login_at=utcnow(),
        expires_at=utcnow().replace(year=2020),
    )
    db.add(expired)
    db.commit()
    assert all(s.id != expired.id for s in svc.list_active_sessions(db, user.id))


def test_revoke_session_blacklists_both_jtis(db, user, monkeypatch):
    import app.core.token_blacklist as bl

    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-9"} if not token.startswith("refresh:") else {"jti": "ref-9"},
    )
    s = svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})

    added = []
    monkeypatch.setattr(bl, "add", lambda jti, expires_at=None: added.append(jti))
    persisted = []
    monkeypatch.setattr(bl, "add_to_db", lambda jti, db_, **kw: persisted.append(jti))

    svc.revoke_session(db, s, operator_id=7, reason="admin_force_logout")

    assert added == ["acc-9", "ref-9"], "access 与 refresh 的 jti 都必须进黑名单"
    assert persisted == ["acc-9", "ref-9"]
    assert s.revoked_at is not None and s.revoked_by == 7 and s.revoke_reason == "admin_force_logout"


def test_update_session_on_refresh_repoints_jti(db, user, monkeypatch):
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1"} if not token.startswith("refresh:") else {"jti": "ref-1"},
    )
    svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})

    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-2"} if not token.startswith("refresh:") else {"jti": "ref-2"},
    )
    updated = svc.update_session_on_refresh(db, "ref-1", {"access_token": "A2", "refresh_token": "refresh:R2"})
    assert updated is not None
    assert updated.token_jti == "acc-2" and updated.refresh_jti == "ref-2"
    # 旧 jti 已不再对应任何会话 → 重复刷新无害
    assert svc.update_session_on_refresh(db, "ref-1", {}) is None


def test_get_session_parses_id_and_scopes_to_user(db, user, monkeypatch):
    monkeypatch.setattr(svc, "_decode", lambda token: {"jti": "acc-1"})
    s = svc.record_login_session(db, user, {"access_token": "A"})
    assert svc.get_session(db, user.id, str(s.id)).id == s.id
    assert svc.get_session(db, user.id, "not-a-number") is None
    assert svc.get_session(db, 999999, s.id) is None  # 他人会话不可见


# ---------------------------------------------------------------------------
# 覆盖率补口（CI 实测缺口：31 / 46-47 / 81-83 / 130 / 158-165 / 194-198 / 200）
# ---------------------------------------------------------------------------
def test_decode_empty_token_returns_empty():
    """空令牌 → 空载荷（不抛错）。"""
    assert svc._decode("") == {}


def test_exp_to_dt_variants():
    """exp 缺失/非法 → None；合法 epoch → aware UTC。"""
    assert svc._exp_to_dt(None) is None
    assert svc._exp_to_dt(0) is None
    assert svc._exp_to_dt("not-a-number") is None
    dt = svc._exp_to_dt(1893456000)  # 2030-01-01 UTC
    assert dt is not None and dt.year == 2030


def test_record_login_swallows_db_errors(db, user, monkeypatch):
    """写库异常被吞掉并返回 None —— 登记是旁路，不得阻断登录。"""
    monkeypatch.setattr(svc, "_decode", lambda token: {"jti": "acc-1"})

    def boom(_db):
        raise RuntimeError("db down")

    monkeypatch.setattr(svc, "safe_commit", boom)
    assert svc.record_login_session(db, user, {"access_token": "A"}) is None


def test_revoke_session_skips_missing_refresh_jti(db, user, monkeypatch):
    """refresh_jti 为 None（如仅 access 的会话）→ continue，不写空 jti。"""
    s = UserSession(user_id=user.id, token_jti="acc-only", login_at=utcnow())
    db.add(s)
    db.commit()
    added = []
    monkeypatch.setattr("app.core.token_blacklist.add", lambda jti, expires_at=None: added.append(jti))
    monkeypatch.setattr("app.core.token_blacklist.add_to_db", lambda *a, **k: None)

    svc.revoke_session(db, s)

    assert added == ["acc-only"]
    assert s.revoked_at is not None


def test_revoke_all_sessions_marks_every_active_row(db, user, monkeypatch):
    """全量吊销：所有活跃会话标记 revoked，返回数量；空列表不触发提交。"""
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1"} if not token.startswith("refresh:") else {"jti": "ref-1"},
    )
    svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})

    n = svc.revoke_all_sessions(db, user.id, operator_id=5)

    assert n == 1
    assert svc.list_active_sessions(db, user.id) == []
    # 再次执行：无活跃会话 → 0，且不提交
    assert svc.revoke_all_sessions(db, user.id, operator_id=5) == 0


def test_update_session_missing_jti_claims_keeps_old_values(db, user, monkeypatch):
    """新令牌缺 jti 声明 → 对应字段保持不变（194->196 / 196->198 假分支）。"""
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1"} if not token.startswith("refresh:") else {"jti": "ref-1"},
    )
    s = svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})

    monkeypatch.setattr(svc, "_decode", lambda token: {})
    svc.update_session_on_refresh(db, "ref-1", {"access_token": "A2", "refresh_token": "refresh:R2"})

    assert s.token_jti == "acc-1" and s.refresh_jti == "ref-1"


def test_update_session_without_exp_keeps_old_expiry(db, user, monkeypatch):
    """新刷新令牌无 exp → expires_at 保持原值（200 行分支）。"""
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1"}
        if not token.startswith("refresh:")
        else {"jti": "ref-1", "exp": 1893456000},
    )
    s = svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})
    before = s.expires_at

    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-2"} if not token.startswith("refresh:") else {"jti": "ref-2"},
    )
    svc.update_session_on_refresh(db, "ref-1", {"access_token": "A2", "refresh_token": "refresh:R2"})

    assert s.token_jti == "acc-2" and s.refresh_jti == "ref-2"
    assert s.expires_at == before


def test_to_dict_contract_aliases(db, user):
    """to_dict 暴露前端契约字段 session_id/created_at（别名）与规范字段。"""
    s = UserSession(user_id=user.id, token_jti="acc-1", login_at=utcnow())
    db.add(s)
    db.commit()
    d = s.to_dict()
    assert d["session_id"] == s.id and d["id"] == s.id
    assert d["created_at"] == d["login_at"]
    assert d["is_active"] is True and d["last_seen_at"] is None
    assert d["jti"] == "acc-1"


def test_session_cleanup_job_reclaims_expired_and_revoked(db, user, monkeypatch):
    """定时作业：过期行与吊销行被回收，未过期行保留（292-315）。"""
    import app.services.backup_scheduler as sched

    expired = UserSession(
        user_id=user.id, token_jti="old", login_at=utcnow(), expires_at=utcnow().replace(year=2020)
    )
    revoked = UserSession(
        user_id=user.id,
        token_jti="revoked",
        login_at=utcnow(),
        expires_at=utcnow() + timedelta(days=7),
        revoked_at=utcnow().replace(year=2020),
    )
    keep = UserSession(
        user_id=user.id, token_jti="keep", login_at=utcnow(), expires_at=utcnow() + timedelta(days=7)
    )
    db.add_all([expired, revoked, keep])
    db.commit()

    monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(db))
    asyncio.run(sched.session_cleanup_job())

    alive = {s.token_jti for s in db.query(UserSession).all()}
    assert alive == {"keep"}


def test_update_session_writes_new_expiry(db, user, monkeypatch):
    """新刷新令牌带 exp → expires_at 更新为对应 UTC 时间（200 行真分支）。"""
    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-1"}
        if not token.startswith("refresh:")
        else {"jti": "ref-1", "exp": 1893456000},
    )
    s = svc.record_login_session(db, user, {"access_token": "A", "refresh_token": "refresh:R"})

    monkeypatch.setattr(
        svc,
        "_decode",
        lambda token: {"jti": "acc-2"}
        if not token.startswith("refresh:")
        else {"jti": "ref-2", "exp": 1993456000},
    )
    svc.update_session_on_refresh(db, "ref-1", {"access_token": "A2", "refresh_token": "refresh:R2"})

    assert s.expires_at is not None and s.expires_at.year == 2033


def test_session_cleanup_job_noop_when_nothing_to_reclaim(db, user, monkeypatch):
    """无可回收行 → 不触发日志/提交（312->exit 分支）。"""
    import app.services.backup_scheduler as sched

    keep = UserSession(
        user_id=user.id, token_jti="keep", login_at=utcnow(), expires_at=utcnow() + timedelta(days=7)
    )
    db.add(keep)
    db.commit()

    monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(db))
    asyncio.run(sched.session_cleanup_job())

    assert {s.token_jti for s in db.query(UserSession).all()} == {"keep"}


def test_session_cleanup_job_swallows_db_errors(db, user, monkeypatch):
    """查询异常 → 记日志不抛出（314-315 except 分支），调度器不被拖垮。"""
    import app.services.backup_scheduler as sched

    monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(db))
    monkeypatch.setattr(
        type(db), "query", lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    asyncio.run(sched.session_cleanup_job())  # 不应抛出
