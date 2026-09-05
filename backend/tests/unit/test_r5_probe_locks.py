"""R5 探针缺陷锁定（2026-09-05）：真实 DB 回归。

1. 奖学金导入字段映射坏死 — 旧实现按 name/student_id/school_name 构造
   ScholarshipStudent（真实列是 student_name + 必填 school_id FK），每行必抛
   TypeError → imported=0。锁定：导入后真实落库 student_name/school_id/remarks。
2. RuralWork 悬挂 village_id → 500（FK 约束失败未处理）。锁定：400 + 明细；
   合法 villages 表 id 创建成功。
"""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Base
from app.models.school import School, SchoolType


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

    async def _override_get_db():
        yield db_session

    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _override_get_db
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
    admin.org_id = 1

    async def _mock_user():
        return admin

    client.app.dependency_overrides[get_current_user] = _mock_user
    yield client


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestScholarshipImportMapping:
    def test_import_lands_with_real_columns(self, auth_setup, db_session):
        """修复锁定：按模型真实列（student_name/school_id/remarks）落库。"""
        school = School(
            name="锁定中学", code="LOCK-01",
            type=SchoolType.MIDDLE,
        )
        db_session.add(school)
        db_session.commit()
        db_session.refresh(school)

        xlsx = _xlsx([
            ["序号", "姓名", "学号", "年份", "金额", "学校", "年级", "事由", "状态"],
            [1, "锁定学生甲", "S2026999", 2026, 3000, "锁定中学", "初三", "品学兼优", "已发放"],
        ])
        resp = auth_setup.post(
            "/api/v1/schools/scholarship/import",
            files={"file": ("stu.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200, resp.text[:300]
        body = resp.json()
        data = body.get("data") or body
        assert data.get("imported") == 1, data

        from app.models.school import ScholarshipStudent

        row = db_session.query(ScholarshipStudent).filter_by(student_name="锁定学生甲").first()
        assert row is not None, "导入数据必须真实落库"
        assert row.school_id == school.id
        assert row.year == 2026
        assert row.amount == 3000
        assert "S2026999" in (row.remarks or "")

    def test_unknown_school_row_rejected_with_detail(self, auth_setup, db_session):
        xlsx = _xlsx([
            ["序号", "姓名", "学号", "年份", "金额", "学校", "年级", "事由", "状态"],
            [1, "锁定学生乙", None, 2026, 1000, "不存在的学校", "初一", "", ""],
        ])
        resp = auth_setup.post(
            "/api/v1/schools/scholarship/import",
            files={"file": ("stu.xlsx", xlsx,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data") or body
        assert data.get("imported") == 0 and data.get("failed") == 1
        assert "学校不存在" in str(data.get("errors"))


class TestRuralWorkVillageGuard:
    def test_dangling_village_id_400_not_500(self, auth_setup):
        """悬挂 village_id 必须 400 + 明细，不得裸 IntegrityError 500。"""
        resp = auth_setup.post(
            "/api/v1/rural-works",
            json={"name": "锁定悬挂工作", "village_id": 99999},
        )
        assert resp.status_code == 400, resp.text[:300]
        assert "村庄不存在" in str(resp.json())

    def test_valid_villages_table_id_creates(self, auth_setup, db_session):
        """合法 villages 表 id（FK 目标表）创建成功。"""
        from app.models.rural_work import RuralWork
        from app.models.village import Village

        v = Village(name="锁定工作村")
        db_session.add(v)
        db_session.commit()
        db_session.refresh(v)

        resp = auth_setup.post(
            "/api/v1/rural-works",
            json={"name": "锁定合法工作", "village_id": v.id},
        )
        assert resp.status_code == 200, resp.text[:300]

        row = db_session.query(RuralWork).filter_by(name="锁定合法工作").first()
        assert row is not None
        assert row.village_id == v.id

    def test_update_with_dangling_village_id_400(self, auth_setup, db_session):
        """更新路径同样校验：悬挂 village_id → 400（覆盖 update 路由 ValueError 分支）。"""
        from app.models.rural_work import RuralWork

        work = RuralWork(name="锁定待更新工作")
        db_session.add(work)
        db_session.commit()

        resp = auth_setup.put(
            f"/api/v1/rural-works/{work.id}",
            json={"village_id": 424242},
        )
        assert resp.status_code == 400, resp.text[:300]
        assert "村庄不存在" in str(resp.json())

        db_session.expire_all()
        row = db_session.query(RuralWork).filter_by(id=work.id).first()
        assert row.village_id is None, "校验失败时不得部分写入"
