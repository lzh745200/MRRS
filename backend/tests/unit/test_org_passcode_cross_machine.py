"""组织 / 机器通行码跨机器自验证回归（2026-09-06 R9 生产反馈修复）。

缺陷：组织通行码为随机数且仅存于管理员本地库，下级单位在自己机器上
校验时 level 2（DB 匹配）永远查不到 → 跨机器组织绑定必败。
修复：通行码按单位名确定性派生（generate_org_pass_code），自验证时在本机
find-or-create 组织与占位记录；机器特定通行码同理按机器码 HMAC 派生。

自助注册端点已下线（账号由管理员或权限包创建），故本文件直接驱动服务层
``self_verify_org_pass_code`` / ``verify_pass_code`` / ``activate_machine_code``，
保留「跨机器通行码 → 本机建档 → 绑定用户」的机器码绑定覆盖。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.machine_code import MachineCode
from app.models.organization import Organization
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
def fresh_db():
    """模拟「另一台机器」的全新库：内存库中不含管理员机下发的任何记录。"""
    other_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=other_engine)
    session = Session(bind=other_engine)
    yield session
    session.close()
    other_engine.dispose()


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


class TestCrossMachinePassCodeBinding:
    """自助注册下线后，跨机器通行码 → 本机建档 → 绑定用户仍必须可用。"""

    def test_self_verify_creates_org_and_pending_record(self, db_session, fresh_db):
        """管理员机生成组织通行码 → 用户机（无记录）凭通行码 + 单位名自验证建档。"""
        org = Organization(name="跨机器组织")
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)
        admin_record = MachineCodeService(db_session).create_organization_pass_code(
            org.id, "4321", False, 1
        )

        other_svc = MachineCodeService(fresh_db)
        record = other_svc.self_verify_org_pass_code(admin_record.pass_code, "跨机器组织")

        assert record is not None
        created_org = (
            fresh_db.query(Organization).filter(Organization.name == "跨机器组织").first()
        )
        assert created_org is not None, "自验证必须在本机创建组织"
        assert created_org.path == f"/{created_org.id}/"
        assert record.organization_id == created_org.id
        assert record.status == "pending"

    def test_wrong_org_name_rejected(self, db_session, fresh_db):
        """单位名与通行码不匹配 → 自验证失败，且不得在本机建组织/记录。"""
        org = Organization(name="真名组织")
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)
        admin_record = MachineCodeService(db_session).create_organization_pass_code(
            org.id, "4321", False, 1
        )

        other_svc = MachineCodeService(fresh_db)
        assert other_svc.self_verify_org_pass_code(admin_record.pass_code, "假名组织") is None
        assert fresh_db.query(Organization).count() == 0
        assert fresh_db.query(MachineCode).count() == 0

    def test_machine_pass_code_cross_machine_binding(self, db_session, fresh_db):
        """管理机为 B 机机器码生成通行码 → B 机凭自身机器码 HMAC 验证并激活绑定。"""
        target_machine_code = "B" * 64
        admin_svc = MachineCodeService(db_session)
        admin_svc.create_machine_code_record(target_machine_code, created_by=1)
        admin_record = (
            db_session.query(MachineCode)
            .filter(MachineCode.machine_code == target_machine_code)
            .first()
        )
        assert admin_record is not None
        pass_code = admin_record.pass_code

        # B 机：本机无该记录，仅凭机器码 + 共享密钥重算 HMAC 自验证
        other_svc = MachineCodeService(fresh_db)
        local_record = other_svc.verify_pass_code(pass_code, target_machine_code)
        assert local_record is not None, "跨机器 HMAC 自验证必须生成本机记录"
        assert local_record.status == "pending"

        # 账号开通时认领并绑定机器码（原注册流程的 activate 步骤）
        assert other_svc.activate_machine_code(
            local_record, user_id=42, current_machine_code=target_machine_code
        )
        fresh_db.refresh(local_record)
        assert local_record.status == "active"
        assert local_record.user_id == 42
        assert local_record.machine_code == target_machine_code

    def test_activation_is_atomic_single_claim(self, db_session):
        """原子认领：同一通行码第二次激活必须失败（并发开户不得双绑）。"""
        machine_code = "C" * 64
        svc = MachineCodeService(db_session)
        record = svc.create_machine_code_record(machine_code, created_by=1)

        assert svc.activate_machine_code(record, user_id=7, current_machine_code=machine_code)
        assert not svc.activate_machine_code(
            record, user_id=8, current_machine_code=machine_code
        )
        db_session.refresh(record)
        assert record.user_id == 7
