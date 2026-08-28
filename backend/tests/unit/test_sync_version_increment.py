"""回归测试：sync_version 自动递增（增量数据包版本过滤依赖）

自建临时 SQLite + Base.metadata.create_all，不依赖外部 test.db 的 schema 新旧
（曾因外部库缺 deleted_at 列导致 PendingRollbackError，2026-08-29 改造）。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.supported_village import SupportedVillage


def test_sync_version_increments_on_update(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync_ver.db'}")
    Base.metadata.create_all(bind=engine, tables=[SupportedVillage.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        v = SupportedVillage(village_name="sync_ver_test")
        db.add(v)
        db.commit()
        assert v.sync_version == 1, f"新行 sync_version 应为 1，实际 {v.sync_version}"

        v.village_name = "sync_ver_test_2"
        db.commit()
        assert v.sync_version == 2, f"更新后 sync_version 应为 2，实际 {v.sync_version}"

        v.village_name = "sync_ver_test_3"
        db.commit()
        assert v.sync_version == 3, f"再次更新后应为 3，实际 {v.sync_version}"
    finally:
        db.close()
        engine.dispose()
