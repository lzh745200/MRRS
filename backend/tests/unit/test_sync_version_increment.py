"""回归测试：sync_version 自动递增（增量数据包版本过滤依赖）"""
from app.core.database import SessionLocal
from app.models.supported_village import SupportedVillage


def test_sync_version_increments_on_update():
    db = SessionLocal()
    try:
        # 先清理 test.db 中可能残留的 sync_ver_test% 行，避免残留数据影响断言
        db.query(SupportedVillage).filter(SupportedVillage.village_name.like("sync_ver_test%")).delete()
        db.commit()

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
        db.query(SupportedVillage).filter(SupportedVillage.village_name.like("sync_ver_test%")).delete()
        db.commit()
        db.close()
