"""W2-T7 回归：data_sync 导入写入收敛到安全管线。

审计 P1-2（`data_sync_service.py` 裸 ``text()`` INSERT/UPDATE）的两个可复现缺陷：

1. **sync_version 不递增**：裸 SQL 绕过 ORM ``before_update`` 事件与批量更新
   自增钩子（``models/base._bump_sync_version_on_bulk_update`` 只认 Update 语句），
   导入覆盖后的行版本号原地不动 —— 增量包 ``sync_version > since`` 过滤会永久漏行。
2. **无逐条 SAVEPOINT**：单条记录写入失败时，其部分写入不会被回滚（末尾
   ``safe_commit`` 照常固化），且会话一旦进入失败事务状态后续记录连锁失败。

本文件在旧实现上必红，用于锁住修复（写入走类型化语句 + 逐条 SAVEPOINT）。
"""
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import Base
from app.models.policy import Policy
from app.models.supported_village import SupportedVillage
from app.services.data_sync_service import DataSyncService

# 模型注册（保证 real_db_session 的 create_all 覆盖本文件用到的表）
assert SupportedVillage.__tablename__ == "supported_villages"
assert Policy.__tablename__ == "policies"
assert "supported_villages" in Base.metadata.tables


def _service() -> DataSyncService:
    return DataSyncService()


def _raw_row(db, table: str, rid: int) -> dict:
    """以导出侧同款方式取行（raw SELECT：时间列是字符串、布尔是 0/1 整数）。"""
    row = db.execute(text(f"SELECT * FROM {table} WHERE id = :i"), {"i": rid}).mappings().one()
    return dict(row)


class TestImportWritesBumpSyncVersion:
    """验收 1：经导入路径写入的记录 sync_version 递增。"""

    async def test_overwrite_import_bumps_sync_version(self, real_db_session):
        db = real_db_session
        village = SupportedVillage(village_name="原始村名", organization_id=1)
        db.add(village)
        db.commit()
        rid = village.id
        assert village.sync_version == 1

        # 导出包里的记录：全列 + ISO 时间字符串 + 源机 sync_version
        payload = _raw_row(db, "supported_villages", rid)
        payload["village_name"] = "导入更新后的村名"
        assert payload["sync_version"] == 1

        result = await _service()._import_table_data(
            db, "supported_villages", [payload], "overwrite", 1
        )

        assert result == {"total": 1, "success": 1, "failed": 0, "conflicts": []}
        db.expire_all()
        stored = db.query(SupportedVillage).filter(SupportedVillage.id == rid).one()
        assert stored.village_name == "导入更新后的村名"
        assert stored.sync_version == 2, (
            "导入覆盖必须递增 sync_version（裸 SQL 路径不会触发递增 → 增量同步永久漏行）"
        )

    async def test_merge_import_bumps_sync_version(self, real_db_session):
        """merge（前端默认策略）分支同样必须递增版本号。"""
        db = real_db_session
        village = SupportedVillage(village_name="原始村名", organization_id=1)
        db.add(village)
        db.commit()
        rid = village.id

        payload = _raw_row(db, "supported_villages", rid)
        payload["village_name"] = "合并后的新名"
        payload["updated_at"] = "2099-01-01T00:00:00"  # 晚于本地 → 触发合并更新

        result = await _service()._import_table_data(
            db, "supported_villages", [payload], "merge", 1
        )

        assert result["success"] == 1
        db.expire_all()
        stored = db.query(SupportedVillage).filter(SupportedVillage.id == rid).one()
        assert stored.village_name == "合并后的新名"
        assert stored.sync_version == 2

    async def test_import_package_end_to_end_bumps_sync_version(self, real_db_session, tmp_path):
        """经公共入口 `import_package` 导入同样递增（调用方链路不被内部改动绕过）。"""
        db = real_db_session
        village = SupportedVillage(village_name="端到端原始", organization_id=1)
        db.add(village)
        db.commit()
        rid = village.id
        payload = _raw_row(db, "supported_villages", rid)
        payload["village_name"] = "端到端导入后"

        package_file = tmp_path / "w2t7.zip"
        package_file.write_bytes(b"pkg")  # 仅需 exists()；解析由 _load_import_package 替身接管

        svc = _service()

        @contextmanager
        def _fake_db_ctx():
            yield db

        svc._get_db_context = _fake_db_ctx
        with patch.object(
            svc,
            "_load_import_package",
            new=AsyncMock(
                return_value={
                    "export_info": {"package_name": "w2t7"},
                    "data": {"supported_villages": [payload]},
                }
            ),
        ):
            result = await svc.import_package(str(package_file), strategy="overwrite")

        assert result["success"] is True
        assert result["success_records"] == 1
        db.expire_all()
        stored = db.query(SupportedVillage).filter(SupportedVillage.id == rid).one()
        assert stored.village_name == "端到端导入后"
        assert stored.sync_version == 2


class TestImportInsertPath:
    """插入路径走类型化写入（保留原始 id/时间列，不因时间字符串整条失败）。"""

    async def test_insert_keeps_raw_export_payload(self, real_db_session):
        db = real_db_session
        source = SupportedVillage(village_name="源村", organization_id=1)
        db.add(source)
        db.commit()

        payload = _raw_row(db, "supported_villages", source.id)
        payload["id"] = 5001
        payload["village_name"] = "复制村"

        result = await _service()._import_table_data(
            db, "supported_villages", [payload], "skip", 1
        )

        assert result == {"total": 1, "success": 1, "failed": 0, "conflicts": []}
        db.expire_all()
        copied = db.query(SupportedVillage).filter(SupportedVillage.id == 5001).one()
        assert copied.village_name == "复制村"
        assert copied.sync_version == payload["sync_version"]  # 新行沿用导出源机版本号

    async def test_update_on_table_without_sync_version_column(self, real_db_session):
        """无 sync_version 列的表（如 policies）不得被强行补列。"""
        db = real_db_session
        policy = Policy(title="原政策")
        db.add(policy)
        db.commit()
        pid = policy.id

        await _service()._update_record(db, "policies", {"id": pid, "title": "更新后政策"})

        db.expire_all()
        stored = db.query(Policy).filter(Policy.id == pid).one()
        assert stored.title == "更新后政策"

    async def test_write_rejects_table_without_model_metadata(self, real_db_session):
        """白名单里的幽灵表名（无模型元数据）必须显式失败，不能拼裸 SQL 打到不存在的表。"""
        with pytest.raises(ValueError, match="未找到表 update_logs 的模型元数据"):
            await _service()._insert_record(real_db_session, "update_logs", {"id": 1})


class TestPerRecordSavepoint:
    """验收 2：单条记录失败仅跳过该条，其余照常导入；失败条目的写入随 savepoint 回滚。"""

    async def test_constraint_violation_skips_only_bad_record(self, real_db_session):
        db = real_db_session
        records = [
            {"id": 9101, "village_name": "第一条", "is_active": 1},
            {"id": 9102, "village_name": None, "is_active": 1},  # NOT NULL 违约
            {"id": 9103, "village_name": "第三条", "is_active": 1},
        ]

        result = await _service()._import_table_data(
            db, "supported_villages", records, "skip", 1
        )

        assert result["total"] == 3
        assert result["success"] == 2
        assert result["failed"] == 1
        db.expire_all()
        ids = sorted(
            v.id
            for v in db.query(SupportedVillage)
            .filter(SupportedVillage.id.in_([9101, 9103]))
            .all()
        )
        assert ids == [9101, 9103]
        assert db.query(SupportedVillage).filter(SupportedVillage.id == 9102).first() is None
        # 会话未被留在 pending-rollback 状态：同一会话继续读/写均正常
        assert db.execute(text("SELECT COUNT(*) FROM supported_villages")).scalar() == 2

    async def test_partial_write_of_failed_record_is_rolled_back(self, real_db_session):
        """保存点语义：失败条目的部分写入必须回滚，不得被末尾 commit 固化。

        旧实现（无逐条 SAVEPOINT）下这条"写了一半再失败"的行会被
        `_import_table_data` 末尾的 safe_commit 固化 → 本用例必红。
        """
        db = real_db_session
        svc = _service()
        real_insert = svc._insert_record

        async def _insert_then_fail(db_, table_name, record):
            await real_insert(db_, table_name, record)  # 先落一半写入
            raise IntegrityError("INSERT ...", {}, Exception("约束冲突"))

        with patch.object(
            svc, "_insert_record", new=AsyncMock(side_effect=_insert_then_fail)
        ):
            result = await svc._import_table_data(
                db,
                "supported_villages",
                [{"id": 9201, "village_name": "部分写入", "is_active": 1}],
                "skip",
                1,
            )

        assert result["success"] == 0
        assert result["failed"] == 1
        db.expire_all()
        assert db.query(SupportedVillage).filter(SupportedVillage.id == 9201).first() is None, (
            "失败条目的部分写入必须随 SAVEPOINT 回滚"
        )


class TestRecordDatetimeCoercion:
    """类型化写入的前置：导出侧 ISO 时间字符串 → datetime（SQLite 方言只收 datetime）。"""

    def test_string_with_offset_is_normalized_to_naive_utc(self):
        parsed = DataSyncService._parse_datetime("2024-06-01T12:00:00+08:00")
        assert parsed == datetime(2024, 6, 1, 4, 0, 0)
        assert parsed.tzinfo is None

    def test_zulu_suffix_is_supported(self):
        assert DataSyncService._parse_datetime("2024-06-01T12:00:00Z") == datetime(
            2024, 6, 1, 12, 0, 0
        )

    def test_naive_string_is_kept_as_utc_wall_clock(self):
        parsed = DataSyncService._parse_datetime("2024-06-01 12:00:00")
        assert parsed == datetime(2024, 6, 1, 12, 0, 0)
        assert parsed.tzinfo is None

    def test_unparseable_string_is_passed_through_for_binder_to_reject(self):
        assert DataSyncService._parse_datetime("不是时间") == "不是时间"

    def test_coercion_keeps_non_datetime_and_unknown_columns_untouched(self):
        table = SupportedVillage.__table__
        payload = {"village_name": "村名", "ghost_column": "2024-01-01T00:00:00"}
        assert DataSyncService._coerce_datetime_values(table, payload) == payload

    async def test_bad_datetime_string_fails_only_that_record(self, real_db_session):
        """脏时间串不再以"原样入库"污染列，而是计为该条失败，其余记录照常导入。"""
        db = real_db_session
        records = [
            {"id": 9301, "village_name": "好记录", "is_active": 1},
            {"id": 9302, "village_name": "坏记录", "is_active": 1, "created_at": "坏时间"},
        ]

        result = await _service()._import_table_data(
            db, "supported_villages", records, "skip", 1
        )

        assert result["success"] == 1
        assert result["failed"] == 1
        db.expire_all()
        assert db.query(SupportedVillage).filter(SupportedVillage.id == 9301).first() is not None
        assert db.query(SupportedVillage).filter(SupportedVillage.id == 9302).first() is None
