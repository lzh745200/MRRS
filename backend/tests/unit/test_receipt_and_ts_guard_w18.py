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
    return {"id": vid, "village_name": name, "organization_id": org, "is_active": True}


class TestReceiptCountingD4:
    """D4：imported 必须等于真实写入行数。"""

    def test_do_nothing_is_not_counted_as_imported(self, db, svc):
        """核心缺陷：非覆盖模式撞 id → DO NOTHING → 不得计为 imported。"""
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="已有村", organization_id=1, is_active=True))
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
    """D5：ts_guard 下旧包不得覆盖本机新编辑。"""

    def test_old_package_cannot_overwrite_newer_local(self, db, svc):
        """核心：包内 updated_at 早于本地 → 守卫拦下，本地内容保持。"""
        from datetime import datetime, timedelta, timezone

        from app.models.supported_village import SupportedVillage

        now = datetime.now(timezone.utc)
        db.add(SupportedVillage(
            id=1, village_name="版本2-本地新编辑", organization_id=1,
            is_active=True, updated_at=now,
        ))
        db.commit()

        old_record = _rec(1, "版本1-包内旧值")
        old_record["updated_at"] = now - timedelta(hours=2)
        imp, skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [old_record], org_id=1, overwrite=True, ts_guard=True,
        )
        db.commit()

        row = db.query(SupportedVillage).filter(SupportedVillage.id == 1).one()
        assert row.village_name == "版本2-本地新编辑"   # 本地新编辑未被覆盖
        assert imp == 0                                  # 守卫拦下（DO NOTHING）

    def test_newer_package_overwrites_with_guard(self, db, svc):
        """包内记录比本地新 → 守卫放行（正常增量语义）。"""
        from datetime import datetime, timedelta, timezone

        from app.models.supported_village import SupportedVillage

        now = datetime.now(timezone.utc)
        db.add(SupportedVillage(
            id=1, village_name="版本1", organization_id=1,
            is_active=True, updated_at=now - timedelta(hours=3),
        ))
        db.commit()

        newer = _rec(1, "版本2-包内更新")
        newer["updated_at"] = now
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [newer], org_id=1, overwrite=True, ts_guard=True,
        )
        db.commit()
        row = db.query(SupportedVillage).filter(SupportedVillage.id == 1).one()
        assert row.village_name == "版本2-包内更新"
        assert imp == 1

    def test_no_guard_keeps_legacy_overwrite(self, db, svc):
        """ts_guard=False（全量包显式覆盖）保持旧语义：无条件覆盖。"""
        from datetime import datetime, timedelta, timezone

        from app.models.supported_village import SupportedVillage

        now = datetime.now(timezone.utc)
        db.add(SupportedVillage(
            id=1, village_name="本地较新", organization_id=1,
            is_active=True, updated_at=now,
        ))
        db.commit()

        old = _rec(1, "包内旧值")
        old["updated_at"] = now - timedelta(hours=5)
        imp, _skip, errs = svc._bulk_upsert_records(
            SupportedVillage, [old], org_id=1, overwrite=True, ts_guard=False,
        )
        db.commit()
        row = db.query(SupportedVillage).filter(SupportedVillage.id == 1).one()
        assert row.village_name == "包内旧值"     # 无守卫时旧包照样覆盖（显式选择）
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