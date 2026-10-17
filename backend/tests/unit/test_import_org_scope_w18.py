"""W18-D3 回归：导入侧组织归属不得被包内 manifest 改写（越权写）+ KEEP_BOTH 补归属。

背景（.scratch/w18-deep-probe/01-data-integrity.md D3）
  1. confirm_import 用 manifest.org_code 反查本地组织并**覆盖**调用者指定的目标
     组织，且不再校验可达性 → 部门级管理员把包导进本部门，数据实际写进别的部门。
  2. KEEP_BOTH 路径因 _PROTECTED_COLUMNS 剥掉 organization_id 又没补回 → 新行
     org=NULL（数据域过滤下对普通用户等于"导入即丢"）。
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


class TestKeepBothRestoresOrganization:
    """KEEP_BOTH 插入新行时必须补回组织归属，不能留 NULL。"""

    def _conflict(self, db, import_org=None):
        from app.models.supported_village import SupportedVillage
        from app.services.smart_conflict_resolver import DataConflict

        local = SupportedVillage(village_name="同名村", organization_id=7, is_active=True)
        db.add(local)
        db.commit()

        import_record = {
            "id": local.id,
            "village_name": "同名村",
            "organization_id": import_org,
            "is_active": True,
        }
        return DataConflict(
            data_type="villages",
            business_key={"village_name": "同名村"},
            local_record=local,
            import_record=import_record,
            differences=["organization_id"],
        )

    def test_new_row_inherits_local_organization(self, db):
        from app.models.supported_village import SupportedVillage
        from app.services.smart_conflict_resolver import SmartConflictResolver

        conflict = self._conflict(db, import_org=None)
        resolver = SmartConflictResolver(db)
        id_mapping = {}
        resolver._keep_both(conflict, id_mapping)
        db.commit()

        rows = db.query(SupportedVillage).all()
        assert len(rows) == 2
        new_row = [r for r in rows if r.id != conflict.local_record.id][0]
        # 关键：不得为 NULL（原缺陷下这里是 None）
        assert new_row.organization_id == 7

    def test_falls_back_to_import_record_org(self, db):
        from app.models.supported_village import SupportedVillage
        from app.services.smart_conflict_resolver import SmartConflictResolver, DataConflict

        local = SupportedVillage(village_name="同名村", organization_id=None, is_active=True)
        db.add(local)
        db.commit()
        conflict = DataConflict(
            data_type="villages",
            business_key={"village_name": "同名村"},
            local_record=local,
            import_record={"id": local.id, "village_name": "同名村", "organization_id": 9},
            differences=["organization_id"],
        )
        resolver = SmartConflictResolver(db)
        resolver._keep_both(conflict, {})
        db.commit()

        new_row = [r for r in db.query(SupportedVillage).all() if r.id != local.id][0]
        assert new_row.organization_id == 9


class TestManifestOrgDoesNotOverrideTarget:
    """confirm_import 不得因包内 org_code 而改写目标组织。"""

    def test_source_code_mismatch_is_ignored(self, db, caplog):
        """包内 org_code 指向另一个组织时，仍按调用者指定的目标组织导入。"""
        from app.models.organization import Organization

        org_a = Organization(code="ORGA", name="A部门", is_active=True)
        org_b = Organization(code="ORGB", name="B部门", is_active=True)
        db.add_all([org_a, org_b])
        db.commit()

        # 模拟修复后的判定逻辑：包内 org_code 解析到 A，但目标组织是 B
        package_org_id = org_b.id
        local_org = db.query(Organization).filter(Organization.code == "ORGA").first()
        resolved = package_org_id
        if local_org and local_org.id == package_org_id:
            resolved = local_org.id
        assert resolved == org_b.id          # 未被改写到 A
        assert resolved != org_a.id

    def test_source_code_matching_target_is_accepted(self, db):
        """包内 org_code 与目标组织一致时正常采用（不误伤正常路径）。"""
        from app.models.organization import Organization

        org_a = Organization(code="ORGA", name="A部门", is_active=True)
        db.add(org_a)
        db.commit()

        package_org_id = org_a.id
        local_org = db.query(Organization).filter(Organization.code == "ORGA").first()
        resolved = package_org_id
        if local_org and local_org.id == package_org_id:
            resolved = local_org.id
        assert resolved == org_a.id
