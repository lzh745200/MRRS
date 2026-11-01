"""API-01（2026-11-01 审计）：主键碰撞换 id 后必须重写子表外键。

缺陷：``_bulk_upsert_records`` 在「主键已被本机另一条业务记录占用」时会给导入
记录换新 id 插入，但旧实现**不登记 源id→新id 映射**，子表记录仍带着包里的旧
父 id —— 项目挂到本机同 id 的另一条村下（数据挂错组织），或父记录换 id 后子
记录成孤儿，而导入回执依旧 success=True。

修法：换 id 时把映射写进 ``remap``（``{表名: {旧主键: 新主键}}``），导入子表前
由 ``_apply_fk_remap`` 重写外键列。本文件用真实 SQLite 验证（冲突分支只在
两个独立库之间显形）。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _service(db):
    from app.services.data_package_service import DataPackageService

    return DataPackageService(db)


def _village(name, org_id=1):
    return {
        "id": 1,
        "village_name": name,
        "organization_id": org_id,
        "province": "贵州省",
        "city": "黔南州",
        "county": "长顺县",
        "township": "示范镇",
        "is_active": 1,
    }


class TestIdRemapOnPrimaryKeyCollision:
    def test_collision_is_recorded_in_remap(self, db):
        """父表（帮扶村）换 id 时必须登记映射；否则子表无从重写。"""
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="B机的真实村", organization_id=2, is_active=True))
        db.commit()

        svc = _service(db)
        remap = {}
        imported, _skipped, errors = svc._bulk_upsert_records(
            SupportedVillage, [_village("A机的另一个村")], org_id=1, overwrite=True, remap=remap
        )

        assert errors == []
        assert imported == 1
        assert set(remap) == {"supported_villages"}
        new_id = remap["supported_villages"][1]
        assert new_id != 1
        row = db.query(SupportedVillage).filter(SupportedVillage.id == new_id).one()
        assert row.village_name == "A机的另一个村"

    def test_child_fk_rewritten_to_new_parent_id(self, db):
        """项目记录的 village_id 必须跟着父村的换 id 一起重写。"""
        from app.models.project import Project
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="B机的真实村", organization_id=2, is_active=True))
        db.commit()

        svc = _service(db)
        remap = {}
        svc._bulk_upsert_records(
            SupportedVillage, [_village("A机的另一个村")], org_id=1, overwrite=True, remap=remap
        )

        new_village_id = remap["supported_villages"][1]
        child = {"id": 5, "project_name": "项目", "village_id": 1, "organization_id": 1}
        rewritten = svc._apply_fk_remap(Project, [child], remap)

        assert rewritten == 1
        assert child["village_id"] == new_village_id

    def test_fund_project_id_rewritten(self, db):
        """两级链路：经费的 project_id 依赖项目换 id。"""
        from app.models.fund import Fund

        svc = _service(db)
        remap = {"projects": {9: 109}}
        child = {"id": 3, "project_id": 9, "amount": 1000, "organization_id": 1}

        assert svc._apply_fk_remap(Fund, [child], remap) == 1
        assert child["project_id"] == 109

    def test_unmapped_values_and_non_fk_columns_untouched(self, db):
        from app.models.project import Project

        svc = _service(db)
        remap = {"supported_villages": {1: 77}}
        child = {"id": 5, "village_id": 2, "organization_id": 1, "project_name": "项目"}

        assert svc._apply_fk_remap(Project, [child], remap) == 0
        assert child["village_id"] == 2
        assert child["project_name"] == "项目"

    def test_empty_remap_is_noop(self, db):
        from app.models.project import Project

        svc = _service(db)
        record = {"id": 5, "village_id": 1}

        assert svc._apply_fk_remap(Project, [record], {}) == 0
        assert svc._apply_fk_remap(Project, [], {"supported_villages": {1: 2}}) == 0
        assert record["village_id"] == 1
