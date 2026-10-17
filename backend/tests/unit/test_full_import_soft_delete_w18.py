"""W18-D2 回归：全量覆盖导入不得物理删除（尤其不得级联抹掉子表）。

背景（.scratch/w18-deep-probe/01-data-integrity.md D2）
  `_import_full_mode` 及同型三处用 `query.delete()` 物理删除，且不过滤 is_active：
    1. 连回收站里的软删行一起物理抹掉（彻底不可恢复）；
    2. projects.village_id / funds.project_id / funds.village_id 是 ON DELETE CASCADE
       —— 只导入「帮扶村」一张表，也会把项目与经费一起物理删除。

修复口径：改为软删除（is_active=False）。数据可从回收站恢复，且不触发级联。
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
    # 外键级联需要显式开启（SQLite 默认关闭）——这正是原缺陷能造成级联删除的前提
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed_chain(db):
    """建一条 村 → 项目 → 经费 的依赖链。"""
    from app.models.fund import Fund
    from app.models.project import Project
    from app.models.supported_village import SupportedVillage

    village = SupportedVillage(village_name="待覆盖村", organization_id=1, is_active=True)
    db.add(village)
    db.flush()
    project = Project(name="关联项目", organization_id=1, is_active=True, village_id=village.id)
    db.add(project)
    db.flush()
    fund = Fund(name="关联经费", organization_id=1, is_active=True,
                amount=100.0, project_id=project.id, village_id=village.id)
    db.add(fund)
    db.commit()
    return village, project, fund


class TestFullImportDoesNotCascadeDelete:
    def test_soft_delete_keeps_children_alive(self, db):
        """核心：清空帮扶村后，关联项目与经费必须仍然存在。"""
        from app.models.fund import Fund
        from app.models.project import Project
        from app.models.supported_village import SupportedVillage
        from app.services.excel_importer_service import ExcelImporterService

        village, project, fund = _seed_chain(db)
        svc = ExcelImporterService(db, current_user=None)

        affected = svc._soft_delete_scoped(SupportedVillage)
        db.commit()

        assert affected == 1
        # 村被软删（不是物理删除）
        row = db.query(SupportedVillage).filter(SupportedVillage.id == village.id).one()
        assert row.is_active in (False, 0)
        # 子表必须完好（原缺陷下这里会变 0）
        assert db.query(Project).count() == 1
        assert db.query(Fund).count() == 1

    def test_soft_delete_does_not_touch_already_deleted_rows(self, db):
        """回收站里的行不被重复处理（原实现会把它们物理抹掉）。"""
        from app.models.supported_village import SupportedVillage
        from app.services.excel_importer_service import ExcelImporterService

        active = SupportedVillage(village_name="在册村", organization_id=1, is_active=True)
        recycled = SupportedVillage(village_name="回收站村", organization_id=1, is_active=False)
        db.add_all([active, recycled])
        db.commit()

        svc = ExcelImporterService(db, current_user=None)
        affected = svc._soft_delete_scoped(SupportedVillage)
        db.commit()

        assert affected == 1                      # 只处理可见行
        assert db.query(SupportedVillage).count() == 2   # 两行都还在（未被物理删除）


class TestProgramsAndFundsSoftDelete:
    def test_project_soft_delete_keeps_funds(self, db):
        from app.models.fund import Fund
        from app.models.project import Project
        from app.services.excel_importer_service import ExcelImporterService

        _village, project, _fund = _seed_chain(db)
        svc = ExcelImporterService(db, current_user=None)

        svc._soft_delete_scoped(Project)
        db.commit()

        assert db.query(Fund).count() == 1        # 经费不因项目软删而消失
        row = db.query(Project).filter(Project.id == project.id).one()
        assert row.is_active in (False, 0)

    def test_fund_soft_delete_is_reversible(self, db):
        from app.models.fund import Fund
        from app.services.excel_importer_service import ExcelImporterService

        _v, _p, fund = _seed_chain(db)
        svc = ExcelImporterService(db, current_user=None)

        svc._soft_delete_scoped(Fund)
        db.commit()

        row = db.query(Fund).filter(Fund.id == fund.id).one()   # 行仍在（可恢复）
        assert row.is_active in (False, 0)
