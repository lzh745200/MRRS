"""W18-D1 回归：跨机数据包导入的主键碰撞（不可逆覆写）。

背景（.scratch/w18-deep-probe/01-data-integrity.md D1）
  数据包导出包含自增 id，两台机器都从 id=1 起步。原实现以源机 id 作
  ON CONFLICT 键：overwrite=True 时把目标机同 id 的真实记录整体覆写成源机
  数据（organization_id/created_at 一并改写，不可逆）；overwrite=False 时
  DO NOTHING 静默丢弃导入记录却仍报成功。

  修复后口径：主键在本库空闲 → 直接插入；主键已占用 → 按业务键判定：
    · 业务键相同 → 同一业务记录，按 overwrite 更新或跳过；
    * 业务键不同 → 是另一条记录撞了 id → 换新 id 插入，不覆写本机数据。

为什么必须用真实 SQLite：缺陷只在"两个独立库"之间显形，单库或全 mock 的
用例根本走不到冲突分支（这也正是它长期没被发现的原因）。
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


def _village(name, org_id):
    from app.models.supported_village import SupportedVillage

    return {
        "id": 1,
        "village_name": name,
        "organization_id": org_id,
        "is_active": 1,
    }


class TestPrimaryKeyCollisionAcrossMachines:
    """两台机器都从 id=1 起步时的导入行为。"""

    def test_overwrite_does_not_destroy_local_record_with_different_business_key(self, db):
        """核心缺陷：不同业务记录撞 id 时，本机记录必须**原样保留**。"""
        from app.models.supported_village import SupportedVillage

        # B 机（本机）已有一条真实村，id=1
        db.add(SupportedVillage(id=1, village_name="B机的真实村", organization_id=2, is_active=True))
        db.commit()

        svc = _service(db)
        # A 机的包带来同 id=1、但业务键不同的村
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [_village("A机的另一个村", 1)], org_id=1, overwrite=True
        )
        assert errs == []
        assert imp == 1

        rows = db.query(SupportedVillage).order_by(SupportedVillage.id).all()
        # 修复前这里只有 1 行且被覆写；修复后两行共存
        assert len(rows) == 2
        assert rows[0].village_name == "B机的真实村"
        assert rows[0].organization_id == 2      # 本机归属未被改写
        assert rows[1].village_name == "A机的另一个村"
        assert rows[1].id != 1                   # 源 id 未被沿用

    def test_same_business_key_updates_in_place_when_overwrite(self, db):
        """同一业务记录（村名+组织相同）才允许按主键更新。"""
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="同名村", organization_id=1, is_active=True))
        db.commit()

        svc = _service(db)
        record = _village("同名村", 1)
        record["is_active"] = 0
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [record], org_id=1, overwrite=True
        )
        assert errs == []
        assert imp == 1

        rows = db.query(SupportedVillage).all()
        assert len(rows) == 1
        assert rows[0].is_active in (False, 0)   # 同一条记录被更新

    def test_same_business_key_keeps_local_when_not_overwrite(self, db):
        """非覆盖模式：同一业务记录保持本机值（不被包内数据改写）。"""
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="同名村", organization_id=1, is_active=True))
        db.commit()

        svc = _service(db)
        record = _village("同名村", 1)
        record["is_active"] = 0
        svc._bulk_upsert_records(SupportedVillage, [record], org_id=1, overwrite=False)

        rows = db.query(SupportedVillage).all()
        assert len(rows) == 1
        assert rows[0].is_active is True

    def test_free_primary_key_inserts_directly(self, db):
        """主键空闲时行为不变：直接插入。"""
        from app.models.supported_village import SupportedVillage

        svc = _service(db)
        record = {"id": 77, "village_name": "新来的村", "organization_id": 1, "is_active": True}
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [record], org_id=1, overwrite=False
        )
        assert errs == []
        assert imp == 1
        row = db.query(SupportedVillage).filter(SupportedVillage.id == 77).first()
        assert row is not None and row.village_name == "新来的村"

    def test_relocated_record_keeps_data_intact(self, db):
        """换新 id 插入时，记录内容（除主键外）必须完整保留。"""
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="本机村", organization_id=2, is_active=True))
        db.commit()

        svc = _service(db)
        record = _village("外来村", 1)
        record["county"] = "某县"
        svc._bulk_upsert_records(SupportedVillage, [record], org_id=1, overwrite=True)

        relocated = db.query(SupportedVillage).filter(
            SupportedVillage.village_name == "外来村"
        ).one()
        assert relocated.county == "某县"
        assert relocated.organization_id == 1


class TestBusinessKeyHelper:
    """业务键抽取的边界。"""

    def test_known_model_returns_key_tuple(self):
        from app.models.supported_village import SupportedVillage
        from app.services.data_package_service import _business_key_of

        # W18-D5 修正：业务键只含不可变字段（organization_id）。village_name 可变
        # （改名是增量更新的常见场景），含它会把"同一条记录的更新"误判成两条记录。
        key = _business_key_of(SupportedVillage, {"village_name": "某村", "organization_id": 3})
        assert key == (3,)

    def test_missing_key_part_returns_none(self):
        from app.models.supported_village import SupportedVillage
        from app.services.data_package_service import _business_key_of

        # 缺 organization_id（唯一业务键字段）→ None
        assert _business_key_of(SupportedVillage, {"village_name": "某村"}) is None
        # organization_id 为空串 → None（无法判定租户归属）
        assert _business_key_of(SupportedVillage, {"village_name": "某村", "organization_id": "  "}) is None

    def test_unknown_model_returns_none(self):
        from app.services.data_package_service import _business_key_of

        class Unknown:
            __tablename__ = "not_in_registry"

        assert _business_key_of(Unknown, {"id": 1}) is None
