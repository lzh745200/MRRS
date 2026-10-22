# -*- coding: utf-8 -*-
"""P1：行政区划编码 / 3 级层级 / 关闭自助注册 / 账号解锁 的行为锁定测试。

覆盖率目标：本文件配合既有用例，保证新增分支（编码校验三分支、层级推断三档、
跨级校验、编码锁定、注册开关、公开配置、解锁）全部被执行。
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.organization_code_service import OrganizationCodeService


# ── 1. 编码服务：纯函数分支 ───────────────────────────────────────────
class TestAdminAreaCode:
    @pytest.mark.parametrize("code", ["", "  ", None, "abc", "5200", "5200000"])
    def test_normalize_rejects_invalid(self, code):
        with pytest.raises(ValueError):
            OrganizationCodeService.normalize_admin_code(code)

    def test_normalize_accepts_six_digit_city_code(self):
        assert OrganizationCodeService.normalize_admin_code(" 520100 ") == "520100"

    @pytest.mark.parametrize(
        ("code", "level"),
        [
            ("520000", "level_1"),   # 省级
            ("520100", "level_2"),   # 市州级
            ("520102", "level_3"),   # 县市级
            ("52000", None),         # 长度不足
            ("52AB00", None),        # 非数字
        ],
    )
    def test_infer_level(self, code, level):
        assert OrganizationCodeService.infer_level(code) == level

    @pytest.mark.parametrize(
        ("level", "order"),
        [("level_2", 2), ("2", 2), ("", None), ("level_x", None), (None, None)],
    )
    def test_level_order(self, level, order):
        assert OrganizationCodeService.level_order(level) == order

    def test_validate_code_wraps_normalize(self):
        svc = OrganizationCodeService()
        assert svc.validate_code("520000") is True
        assert svc.validate_code("520") is False


# ── 2. 组织接口：编码必填 / 层级推导 / 跨级 / 锁定 ─────────────────────
@pytest.fixture
def p1_db():
    """本文件专用的内存库：不复用 conftest 的共享会话，避免跨文件数据污染。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_client(db, *, role="super_admin", superuser=True, uid=1):
    from app.main import app

    def _get_db():
        yield db

    user = SimpleNamespace(id=uid, username="admin", role=role, is_superuser=superuser, is_active=True)

    async def _current_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _current_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(p1_db):
    from app.main import app

    original = app.dependency_overrides.copy()
    c = _make_client(p1_db)
    try:
        yield c
    finally:
        app.dependency_overrides = original


class TestOrganizationCodeRules:
    def test_root_must_be_province_code(self, client):
        resp = client.post("/api/v1/organizations", json={"name": "根", "code": "520100"})
        assert resp.status_code == 422
        assert "逐级" in resp.text or "层级" in resp.text

    def test_child_level_must_follow_parent(self, client):
        parent = client.post("/api/v1/organizations", json={"name": "贵州省", "code": "520000"})
        assert parent.status_code in (200, 201), parent.text
        pid = parent.json()["data"]["id"]
        # 直接挂县市级（跨级）→ 422
        resp = client.post(
            "/api/v1/organizations", json={"name": "南明区", "code": "520102", "parent_id": pid}
        )
        assert resp.status_code == 422
        # 正常挂市州级 → 通过
        ok = client.post(
            "/api/v1/organizations", json={"name": "贵阳市", "code": "520100", "parent_id": pid}
        )
        assert ok.status_code in (200, 201), ok.text

    def test_declared_level_must_match_code(self, client):
        resp = client.post(
            "/api/v1/organizations",
            json={"name": "冲突", "code": "520000", "level": "level_2"},
        )
        assert resp.status_code == 422
        assert "不一致" in resp.text

    def test_code_locked_on_update(self, client):
        created = client.post("/api/v1/organizations", json={"name": "贵州省", "code": "520000"})
        oid = created.json()["data"]["id"]
        resp = client.put(f"/api/v1/organizations/{oid}", json={"code": "520001"})
        assert resp.status_code == 422
        assert "锁定" in resp.text

    def test_duplicate_code_rejected(self, client):
        client.post("/api/v1/organizations", json={"name": "贵州省", "code": "520000"})
        dup = client.post("/api/v1/organizations", json={"name": "重复", "code": "520000"})
        assert dup.status_code == 400


# ── 3. 注册开关与公开配置 ─────────────────────────────────────────────
class TestSelfRegisterGate:
    def test_register_closed_by_default(self, client, monkeypatch):
        from app.api.v1.auth import auth as auth_module

        async def _allow(**_kwargs):
            return True

        monkeypatch.setattr(auth_module, "check_rate_limit", _allow)
        monkeypatch.setattr(auth_module, "get_client_ip", lambda _r: "127.0.0.1")
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "newbie", "password": "Str0ng!Pass123", "pass_code": "x"},
        )
        assert resp.status_code == 403
        assert "自助注册" in resp.text

    def test_public_config_reflects_mode(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "SELF_REGISTER_MODE", "off", raising=False)
        off = client.get("/api/v1/auth/public-config")
        assert off.status_code == 200
        assert off.json()["data"]["self_register_enabled"] is False

        monkeypatch.setattr(settings, "SELF_REGISTER_MODE", "controlled", raising=False)
        on = client.get("/api/v1/auth/public-config")
        assert on.json()["data"]["self_register_enabled"] is True


# ── 4. 账号解锁接口 ───────────────────────────────────────────────────
class TestUnlockEndpoint:
    def test_unlock_unknown_user_404(self, client):
        resp = client.post("/api/v1/users/999999/unlock")
        assert resp.status_code == 404

    def test_unlock_requires_admin(self, p1_db):
        from app.main import app

        original = app.dependency_overrides.copy()
        c = _make_client(p1_db, role="user", superuser=False)
        try:
            resp = c.post("/api/v1/users/1/unlock")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides = original

    def test_unlock_success_clears_lock(self, p1_db):
        from app.main import app
        from app.models.user import User

        user = User(
            username="locked_user",
            full_name="锁定用户",
            hashed_password="x",
            role="user",
            is_active=True,
            failed_login_count=5,
        )
        p1_db.add(user)
        p1_db.commit()

        original = app.dependency_overrides.copy()
        c = _make_client(p1_db)
        try:
            resp = c.post(f"/api/v1/users/{user.id}/unlock")
            assert resp.status_code == 200, resp.text
            p1_db.refresh(user)
            assert user.failed_login_count == 0
        finally:
            app.dependency_overrides = original
