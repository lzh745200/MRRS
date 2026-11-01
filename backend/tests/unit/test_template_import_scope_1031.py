"""短期项 3 回归：模板导入按组织 + is_active 解析关联村（2026-11-01 审计）。

历史缺陷：帮扶项目/乡村工作导入按村名裸查 ``supported_villages`` ——
① 跨组织同名村会被错挂（且返回 success=True）；
② 已软删除（is_active=False）的村仍会被命中；
③ 项目导入不落 organization_id，导致数据域 fail-closed 后新记录不可见。

覆盖：
- ``_project_process_rows`` 按组织限定 + 跳过软删村 + 回填 organization_id
- ``_rural_work_process_rows`` 同样按组织限定
- 超管（organization_id=None）不限定组织
- ``_import_scope_org_id`` 的三种身份
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.report_templates import (
    _import_scope_org_id,
    _project_process_rows,
    _rural_work_process_rows,
)
from app.models.base import Base
from app.models.project import Project
from app.models.rural_work import RuralWork
from app.models.supported_village import SupportedVillage


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _village(db, *, name: str, organization_id: int, active: bool = True) -> SupportedVillage:
    village = SupportedVillage(
        village_name=name,
        organization_id=organization_id,
        is_active=active,
    )
    db.add(village)
    db.flush()
    return village


class TestImportScopeOrgId:
    def test_superuser_is_unrestricted(self):
        assert _import_scope_org_id(SimpleNamespace(is_superuser=True, role="super_admin")) is None

    def test_department_admin_uses_own_org(self):
        user = SimpleNamespace(is_superuser=False, role="admin", organization_id=7)
        assert _import_scope_org_id(user) == 7

    def test_missing_user_is_unrestricted(self):
        assert _import_scope_org_id(None) is None


class TestProjectImportVillageScope:
    def test_resolves_only_same_org_village(self, db_session):
        own = _village(db_session, name="同名村", organization_id=1)
        _village(db_session, name="同名村", organization_id=2)

        created, skipped, errors = _project_process_rows(
            db_session,
            [{"name": "道路硬化项目", "village_name": "同名村"}],
            "create",
            set(),
            1,
            organization_id=1,
        )

        assert (created, skipped, errors) == (1, 0, [])
        project = db_session.query(Project).filter(Project.name == "道路硬化项目").one()
        assert project.village_id == own.id
        assert project.organization_id == 1

    def test_skips_soft_deleted_village(self, db_session):
        _village(db_session, name="已删村", organization_id=1, active=False)

        created, _, _ = _project_process_rows(
            db_session,
            [{"name": "无法挂村的项目", "village_name": "已删村"}],
            "create",
            set(),
            1,
            organization_id=1,
        )

        assert created == 1
        project = db_session.query(Project).filter(Project.name == "无法挂村的项目").one()
        assert project.village_id is None

    def test_superuser_unrestricted_uses_any_village(self, db_session):
        other = _village(db_session, name="跨组织村", organization_id=9)

        created, _, _ = _project_process_rows(
            db_session,
            [{"name": "超管导入项目", "village_name": "跨组织村"}],
            "create",
            set(),
            1,
            organization_id=None,
        )

        assert created == 1
        project = db_session.query(Project).filter(Project.name == "超管导入项目").one()
        assert project.village_id == other.id
        # 超管未显式给组织时，项目归属回落到村所属组织
        assert project.organization_id == 9


class TestRuralWorkImportVillageScope:
    def test_resolves_only_same_org_village(self, db_session):
        own = _village(db_session, name="乡村同名村", organization_id=3)
        _village(db_session, name="乡村同名村", organization_id=4)

        created, skipped, errors = _rural_work_process_rows(
            db_session,
            [{"name": "人居环境整治", "village_name": "乡村同名村"}],
            "create",
            set(),
            1,
            organization_id=3,
        )

        assert (created, skipped, errors) == (1, 0, [])
        work = db_session.query(RuralWork).filter(RuralWork.name == "人居环境整治").one()
        assert work.supported_village_id == own.id
