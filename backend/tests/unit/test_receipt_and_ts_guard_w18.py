"""W18-D4/D5 回归：导入回执真实计数 + 增量包时间戳守卫。

D4（回执失真）：原实现 imported 按"组内条数"累计，DO NOTHING 的行一个没写
  也照计数 —— 前端弹"导入成功 3 条"，库里 0 条新数据。改为按 result.rowcount。
D5（增量覆盖）：overwrite_existing=True 无视时间戳，旧增量包把本机新编辑
  打回旧版本。修复：ts_guard=True 时 upsert 加 where excluded.updated_at > local。
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


@pytest.fixture
def svc(db):
    from app.services.data_package_service import DataPackageService

    return DataPackageService(db)


def _rec(vid, name, org=1):
    """导入记录。

    W27：帮扶村业务键改为「组织 + 行政区划 + 村名」（见
    ``data_package_service.BUSINESS_KEYS``），因此必须带行政区划字段 ——
    否则业务键不可判定，记录会被 fail-safe 归入 relocated（新 id 插入），
    本文件的"同一条记录才覆盖"语义就测不到了。
    """
    return {
        "id": vid,
        "village_name": name,
        "organization_id": org,
        "province": "贵州省",
        "city": "黔南州",
        "county": "长顺县",
        "township": "示范镇",
        "is_active": True,
    }


def _local(vid, name, org=1, **kw):
    """本机已有帮扶村（行政区划与 _rec 默认值一致，确保业务键可判定）。"""
    from app.models.supported_village import SupportedVillage

    return SupportedVillage(
        id=vid,
        village_name=name,
        organization_id=org,
        province=kw.pop("province", "贵州省"),
        city=kw.pop("city", "黔南州"),
        county=kw.pop("county", "长顺县"),
        township=kw.pop("township", "示范镇"),
        is_active=kw.pop("is_active", True),
        **kw,
    )


class TestReceiptCountingD4:
    """D4：imported 必须等于真实写入行数。"""

    def test_do_nothing_is_not_counted_as_imported(self, db, svc):
        """核心缺陷：非覆盖模式撞 id → DO NOTHING → 不得计为 imported。"""
        from app.models.supported_village import SupportedVillage

        db.add(_local(1, "已有村"))
        db.commit()

        # 非覆盖模式导入同 id、同业务键（同名村）→ 冲突 → DO NOTHING
        imp, skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [_rec(1, "已有村")], org_id=1, overwrite=False,
        )
        assert errs == []
        assert imp == 0                      # 修复前这里谎报 1
        assert skip == 1                     # 被跳过
        assert db.query(SupportedVillage).count() == 1

    def test_insert_counts_one(self, db, svc):
        """主键空闲 → 插入成功 → imported=1、skipped=0。"""
        from app.models.supported_village import SupportedVillage

        imp, skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [_rec(9, "新来的村")], org_id=1, overwrite=False,
        )
        assert errs == []
        assert imp == 1
        assert skip == 0


class TestTimestampGuardD5:
    """D5：ts_guard 下旧包不得覆盖本机新编辑。

    W27 适配：帮扶村业务键已含**村名**，因此"同一条记录"必须村名相同 —— 本类用
    **非业务键字段** ``department`` 表达"包内值 vs 本机值"，这样才能真正测到
    ts_guard 的放行/拦截语义（此前用不同村名区分新旧值，在旧业务键下等价，
    在含村名的新业务键下会被判为两条不同记录而落到 relocated）。
    """

    def test_old_package_cannot_overwrite_newer_local(self, db, svc):
        """核心：包内 updated_at 早于本地 → 守卫拦下，本地内容保持。"""
        from datetime import datetime, timedelta, timezone

        from app.models.supported_village import SupportedVillage

        now = datetime.now(timezone.utc)
        db.add(_local(1, "同名村", updated_at=now, department="本机新值"))
        db.commit()

        old_record = _rec(1, "同名村")
        old_record["department"] = "包内旧值"
        old_record["updated_at"] = now - timedelta(hours=2)
        imp, skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [old_record], org_id=1, overwrite=True, ts_guard=True,
        )
        db.commit()

        row = db.query(SupportedVillage).filter(SupportedVillage.id == 1).one()
        assert row.department == "本机新值"   # 本机新编辑未被覆盖
        assert imp == 0                       # 守卫拦下（DO NOTHING）

    def test_newer_package_overwrites_with_guard(self, db, svc):
        """包内记录比本地新 → 守卫放行（正常增量语义）。"""
        from datetime import datetime, timedelta, timezone

        from app.models.supported_village import SupportedVillage

        now = datetime.now(timezone.utc)
        db.add(_local(1, "同名村", updated_at=now - timedelta(hours=3), department="本机旧值"))
        db.commit()

        newer = _rec(1, "同名村")
        newer["department"] = "包内新值"
        newer["updated_at"] = now
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [newer], org_id=1, overwrite=True, ts_guard=True,
        )
        db.commit()
        row = db.query(SupportedVillage).filter(SupportedVillage.id == 1).one()
        assert row.department == "包内新值"
        assert imp == 1

    def test_no_guard_keeps_legacy_overwrite(self, db, svc):
        """ts_guard=False（全量包显式覆盖）保持旧语义：无条件覆盖。"""
        from datetime import datetime, timedelta, timezone

        from app.models.supported_village import SupportedVillage

        now = datetime.now(timezone.utc)
        db.add(_local(1, "同名村", updated_at=now, department="本机较新"))
        db.commit()

        old = _rec(1, "同名村")
        old["department"] = "包内旧值"
        old["updated_at"] = now - timedelta(hours=5)
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [old], org_id=1, overwrite=True, ts_guard=False,
        )
        db.commit()
        row = db.query(SupportedVillage).filter(SupportedVillage.id == 1).one()
        assert row.department == "包内旧值"     # 无守卫时旧包照样覆盖（显式选择）
        assert imp == 1

    def test_incremental_endpoint_enables_guard(self):
        """增量应用端点必须开启 ts_guard（契约锁，防止未来回归）。"""
        import io
        import os

        ep = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__),
            )))),
            "backend", "app", "api", "v1", "data", "data", "data_packages.py",
        )
        src = io.open(ep, encoding="utf-8").read()
        # confirm_import(overwrite_existing=True) 的调用点必须带 ts_guard=True
        assert "ts_guard=True" in src