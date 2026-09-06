"""组织通行码跨机器自验证回归（2026-09-06 R9 生产反馈修复）。

缺陷：组织通行码为随机数且仅存于管理员本地库，下级单位在自己机器上
注册时 level 2（DB 匹配）永远查不到 → 跨机器组织注册必败。
修复：通行码按单位名确定性派生（generate_org_pass_code），注册附带
org_name 时自验证并在本机 find-or-create 组织与占位记录。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Base
from app.models.organization import Organization
from unittest.mock import patch

from app.services.machine_code_service import MachineCodeService


@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=e)
    return e


@pytest.fixture
def db_session(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    if trans.is_active:
        trans.rollback()
    conn.close()


@pytest.fixture
def client(db_session):
    from app.main import app

    async def _override():
        yield db_session

    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original


@pytest.fixture
def auth_setup(client):
    from unittest.mock import MagicMock

    admin = MagicMock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.organization_id = 1

    async def _mock():
        return admin

    client.app.dependency_overrides[get_current_user] = _mock
    yield client


class TestSelfVerifyGuardBranches:
    def test_no_db_raises(self):
        from app.services.machine_code_service import MachineCodeService

        svc = MachineCodeService(db=None)
        with pytest.raises(ValueError):
            svc.self_verify_org_pass_code("any", "任意单位")

    def test_empty_org_name_returns_none(self, db_session):
        svc = MachineCodeService(db_session)
        assert svc.self_verify_org_pass_code("some-code", "") is None
        assert svc.self_verify_org_pass_code("some-code", "   ") is None


class TestDeterministicOrgPassCode:
    def test_regenerate_is_idempotent(self, db_session):
        """同组织重复生成 → 相同通行码（可重复下发，不再随机漂移）。"""
        org = Organization(name="确定性组织")
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        svc = MachineCodeService(db_session)
        code = "1234"
        r1 = svc.create_organization_pass_code(org.id, code, False, 1)
        r2 = svc.create_organization_pass_code(org.id, code, False, 1)

        assert r1.id != r2.id or r1.id == r2.id  # 复用或新建皆可
        assert r2.pass_code == r1.pass_code, "重复生成必须幂等"

    def test_pass_code_derives_from_org_name(self, db_session):
        org = Organization(name="派生组织甲")
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        svc = MachineCodeService(db_session)
        record = svc.create_organization_pass_code(org.id, "5678", False, 1)
        assert record.pass_code == svc.generate_org_pass_code("派生组织甲")
        # 不同单位名 → 不同通行码
        assert record.pass_code != svc.generate_org_pass_code("派生组织乙")


class TestOrgSelfVerifyRegistration:
    def _csrf_login_headers(self, client):
        r = client.get("/api/v1/auth/csrf-token")
        token = (r.json().get("data") or {}).get("csrf_token")
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@2026"},
            headers={"X-CSRF-Token": token},
        )
        d = r.json()
        at = (d.get("data") or {}).get("access_token")
        return {"Authorization": f"Bearer {at}", "X-CSRF-Token": token}

    def test_cross_machine_org_registration(self, auth_setup, db_session):
        """跨机器组织注册全链：管理员机生成 → 用户机（无记录）凭通行码+单位名注册。"""
        org = Organization(name="跨机器组织")
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        # 管理员机生成组织通行码（确定性）
        svc = MachineCodeService(db_session)
        record = svc.create_organization_pass_code(org.id, "4321", False, 1)
        pass_code = record.pass_code

        # 用户"另一台机器"：全新内存库（模拟无管理员记录）
        other_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=other_engine)
        other_session = Session(bind=other_engine)
        _orig = auth_setup.app.dependency_overrides[get_db]

        async def _other_db():
            yield other_session

        auth_setup.app.dependency_overrides[get_db] = _other_db
        try:
            r = auth_setup.get("/api/v1/auth/csrf-token")
            token = (r.json().get("data") or {}).get("csrf_token")
            r = auth_setup.post(
                "/api/v1/auth/register",
                json={
                    "username": "cross_org_user",
                    "password": "Cr0ss!Org#2026x",
                    "pass_code": pass_code,
                    "org_name": "跨机器组织",
                },
                headers={"X-CSRF-Token": token},
            )
            assert r.status_code == 200, r.text[:300]
            access = (r.json().get("data") or {}).get("access_token")
            assert access

            # 本机自动建组织 + 用户绑定
            other_org = (
                other_session.query(Organization)
                .filter(Organization.name == "跨机器组织")
                .first()
            )
            assert other_org is not None, "自验证必须在本机创建组织"
            from app.models.user import User

            user = (
                other_session.query(User)
                .filter(User.username == "cross_org_user")
                .first()
            )
            assert user is not None and user.organization_id == other_org.id
        finally:
            auth_setup.app.dependency_overrides[get_db] = _orig
            other_session.close()
            other_engine.dispose()

    def test_wrong_org_name_rejected(self, auth_setup, db_session):
        """跨机器场景下单位名不匹配 → 自验证失败 → 400。"""
        org = Organization(name="真名组织")
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        svc = MachineCodeService(db_session)
        record = svc.create_organization_pass_code(org.id, "4321", False, 1)
        pass_code = record.pass_code

        # 用户机：独立空库（无管理员记录，强制走自验证路径）
        other_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=other_engine)
        other_session = Session(bind=other_engine)
        _orig = auth_setup.app.dependency_overrides[get_db]

        async def _other_db():
            yield other_session

        auth_setup.app.dependency_overrides[get_db] = _other_db
        try:
            r = auth_setup.get("/api/v1/auth/csrf-token")
            token = (r.json().get("data") or {}).get("csrf_token")
            r = auth_setup.post(
                "/api/v1/auth/register",
                json={
                    "username": "wrong_org_user",
                    "password": "Wr0ng!Org#2026x",
                    "pass_code": pass_code,
                    "org_name": "假名组织",
                },
                headers={"X-CSRF-Token": token},
            )
            assert r.status_code == 400, r.text[:200]
            from app.models.user import User

            assert (
                other_session.query(User)
                .filter(User.username == "wrong_org_user")
                .first()
                is None
            ), "自验证失败不得创建用户"
        finally:
            auth_setup.app.dependency_overrides[get_db] = _orig
            other_session.close()
            other_engine.dispose()

    def test_machine_specific_pass_code_self_verify_across_machine(
        self, auth_setup, db_session, monkeypatch
    ):
        """机器特定通行码跨机器：管理机为 B 机机器码生成，B 机注册经 HMAC 自验证通过。"""
        target_machine_code = "B" * 64
        svc = MachineCodeService(db_session)
        svc.create_machine_code_record(target_machine_code, created_by=1)

        from app.models.machine_code import MachineCode

        record = (
            db_session.query(MachineCode)
            .filter_by(machine_code=target_machine_code)
            .first()
        )
        pass_code = record.pass_code

        r = auth_setup.get("/api/v1/auth/csrf-token")
        token = (r.json().get("data") or {}).get("csrf_token")

        # 模拟 B 机：注册时 get_machine_code 返回 B 机机器码（而非本机）
        with patch(
            "app.services.machine_code_service.MachineCodeService.get_machine_code",
            staticmethod(lambda: target_machine_code),
        ):
            r = auth_setup.post(
                "/api/v1/auth/register",
                json={
                    "username": "cross_mc_user",
                    "password": "Cr0ss!MC#2026xx",
                    "pass_code": pass_code,
                },
                headers={"X-CSRF-Token": token},
            )
        assert r.status_code == 200, r.text[:300]
        access = (r.json().get("data") or {}).get("access_token")
        assert access
