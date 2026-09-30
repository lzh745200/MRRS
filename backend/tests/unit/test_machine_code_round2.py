"""OCR 深审第二轮：机器码/组织通行码两处缺陷的回归锁定。

缺陷 1（500）：`hmac.compare_digest` 比较含非 ASCII 的 str 抛 TypeError
（CPython 限制 str 比较仅支持 ASCII）→ 用户输入中文/emoji 通行码即 500。
缺陷 2（UNIQUE 冲突）：pass_code 由单位名确定性派生且列上有 UNIQUE 约束，而
"幂等复用"查询只筛 status == "pending" —— 该组织已有 active/revoked 记录
（或另一同名单位已占用同一通行码）时新建必撞 UNIQUE → IntegrityError 未捕获。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.machine_code import MachineCode
from app.models.organization import Organization
from app.services.machine_code_service import MachineCodeService


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'machine_code.db'}")
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _add_org(session, name: str) -> Organization:
    org = Organization(name=name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


class TestNonAsciiPassCodeDoesNotRaise:
    def test_verify_pass_code_hmac_returns_false_for_non_ascii(self):
        assert MachineCodeService.verify_pass_code_hmac("中文通行码🚀", "MC-ABC") is False

    def test_self_verify_org_pass_code_returns_none_for_non_ascii(self, session_factory):
        session = session_factory()
        svc = MachineCodeService(session)
        assert svc.self_verify_org_pass_code("中文通行码🚀", "某某单位") is None
        session.close()


class TestCreateOrgPassCodeReuseAcrossStatuses:
    def test_active_record_is_reused_instead_of_unique_crash(self, session_factory):
        session = session_factory()
        org = _add_org(session, "已激活单位")
        existing = MachineCode(
            machine_code="ORG-1-existing",
            pass_code="OLD-PASS-CODE",
            status="active",
            organization_id=org.id,
            user_id=7,
        )
        session.add(existing)
        session.commit()

        svc = MachineCodeService(session)
        record = svc.create_organization_pass_code(org.id, "1234", True, 1)

        assert record.id == existing.id, "必须复用同组织记录，而不是新建撞 UNIQUE"
        assert record.status == "pending"
        assert record.user_id is None
        assert session.query(MachineCode).count() == 1
        session.close()

    def test_revoked_record_is_reissued(self, session_factory):
        session = session_factory()
        org = _add_org(session, "已撤销单位")
        existing = MachineCode(
            machine_code="ORG-2-existing",
            pass_code="OLD-PASS-CODE-2",
            status="revoked",
            organization_id=org.id,
        )
        session.add(existing)
        session.commit()

        svc = MachineCodeService(session)
        record = svc.create_organization_pass_code(org.id, "1234", False, 1)

        assert record.id == existing.id
        assert record.status == "pending"
        assert session.query(MachineCode).count() == 1
        session.close()

    def test_same_name_org_shares_deterministic_code_without_unique_crash(self, session_factory):
        session = session_factory()
        first = _add_org(session, "同名单位")
        second = _add_org(session, "同名单位")

        svc = MachineCodeService(session)
        r1 = svc.create_organization_pass_code(first.id, "1111", False, 1)
        r2 = svc.create_organization_pass_code(second.id, "2222", False, 1)

        assert r1.pass_code == r2.pass_code, "同名单位派生同一通行码（确定性派生）"
        assert session.query(MachineCode).count() == 1, "不得因 UNIQUE 约束抛 IntegrityError"
        assert r2.organization_id == second.id
        session.close()

    def test_brand_new_org_creates_record(self, session_factory):
        session = session_factory()
        org = _add_org(session, "全新单位")

        svc = MachineCodeService(session)
        record = svc.create_organization_pass_code(org.id, "9999", False, 1)

        assert record.status == "pending"
        assert record.pass_code == svc.generate_org_pass_code("全新单位")
        assert session.query(MachineCode).count() == 1
        session.close()
