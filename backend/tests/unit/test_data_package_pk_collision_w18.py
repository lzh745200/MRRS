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
    """构造一条帮扶村导入记录。

    W27：业务键改为「组织 + 行政区划 + 村名」（见
    ``data_package_service.BUSINESS_KEYS``），因此这里必须带上行政区划字段 ——
    否则业务键不可判定，记录会被 fail-safe 归入 relocated（新 id 插入）。
    """
    from app.models.supported_village import SupportedVillage  # noqa: F401 - 确保模型注册

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


def _local_village(village_id, name, org_id, **kw):
    """构造一条本机已存在的帮扶村（行政区划与 _village 默认值一致）。"""
    from app.models.supported_village import SupportedVillage

    return SupportedVillage(
        id=village_id,
        village_name=name,
        organization_id=org_id,
        province=kw.get("province", "贵州省"),
        city=kw.get("city", "黔南州"),
        county=kw.get("county", "长顺县"),
        township=kw.get("township", "示范镇"),
        is_active=kw.get("is_active", True),
    )


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
        """同一业务记录（组织 + 行政区划 + 村名相同）才允许按主键更新。"""
        from app.models.supported_village import SupportedVillage

        db.add(_local_village(1, "同名村", 1))
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

        db.add(_local_village(1, "同名村", 1))
        db.commit()

        svc = _service(db)
        record = _village("同名村", 1)
        record["is_active"] = 0
        svc._bulk_upsert_records(SupportedVillage, [record], org_id=1, overwrite=False)

        rows = db.query(SupportedVillage).all()
        assert len(rows) == 1
        assert rows[0].is_active is True

    def test_same_org_but_different_village_never_overwrites_local(self, db):
        """W26-P0-1 核心回归：**同组织**两台机器、主键相撞但村名不同。

        修复前业务键只有 organization_id，同组织必然"判定为同一条"→ 本机真实村
        被源机数据覆写（不可逆）。修复后必须两行共存、本机记录原样保留。
        """
        from app.models.supported_village import SupportedVillage

        db.add(_local_village(1, "B机的真实村", 1))
        db.commit()

        svc = _service(db)
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [_village("A机的村", 1)], org_id=1, overwrite=True
        )
        assert errs == []
        assert imp == 1

        rows = db.query(SupportedVillage).order_by(SupportedVillage.id).all()
        assert len(rows) == 2, "同组织跨机导入不得覆写本机记录"
        assert rows[0].village_name == "B机的真实村"
        assert rows[1].village_name == "A机的村"
        assert rows[1].id != 1

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

    _FULL = {
        "organization_id": 3,
        "province": "贵州省",
        "city": "黔南州",
        "county": "长顺县",
        "township": "示范镇",
        "village_name": "某村",
    }

    def test_known_model_returns_key_tuple(self):
        from app.models.supported_village import SupportedVillage
        from app.services.data_package_service import _business_key_of

        # W27：业务键 = 组织 + 县 + 村名（见 BUSINESS_KEYS 注释）。
        # 旧实现只有 organization_id —— 同组织内恒相同，导致跨机导入必覆写（P0-1）。
        key = _business_key_of(SupportedVillage, self._FULL)
        assert key == (3, "长顺县", "某村")

    def test_key_is_stable_regardless_of_dict_order(self):
        from app.models.supported_village import SupportedVillage
        from app.services.data_package_service import _business_key_of

        reversed_dict = dict(reversed(list(self._FULL.items())))
        assert _business_key_of(SupportedVillage, self._FULL) == _business_key_of(
            SupportedVillage, reversed_dict
        )

    def test_missing_key_part_returns_none(self):
        from app.models.supported_village import SupportedVillage
        from app.services.data_package_service import _business_key_of

        # 缺 organization_id → None
        rec = dict(self._FULL)
        rec.pop("organization_id")
        assert _business_key_of(SupportedVillage, rec) is None
        # 业务键三要素任一为空 → None（不可判定 → 由调用方按 relocated 处理）
        for field in ("organization_id", "county", "village_name"):
            partial = dict(self._FULL)
            partial[field] = "  "
            assert _business_key_of(SupportedVillage, partial) is None, f"{field} 空白时应不可判定"
        # 非业务键字段缺失不影响判定（乡镇常缺填，不能因此退化为 relocated）
        partial = {k: v for k, v in self._FULL.items() if k != "township"}
        assert _business_key_of(SupportedVillage, partial) == (3, "长顺县", "某村")

    def test_unknown_model_returns_none(self):
        from app.services.data_package_service import _business_key_of

        class Unknown:
            __tablename__ = "not_in_registry"

        assert _business_key_of(Unknown, {"id": 1}) is None
