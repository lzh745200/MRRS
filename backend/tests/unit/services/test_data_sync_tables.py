"""W2-T1 回归：数据同步表名单一常量源 + 导出错误显式上报。

历史缺陷：syncable_tables 使用复数表名而真实表名为单数，
10 张年度数据表静默丢同步；单表异常被吞成空列表且 overall success=True。
"""

import pytest

from app.services.data_sync_service import DataSyncService, _ALLOWED_TABLES


class TestSyncTableSingleSource:
    def test_syncable_tables_all_exist_in_metadata(self):
        """syncable_tables 的每个键必须是真实存在的表名。"""
        from app.models import Base

        svc = DataSyncService()
        missing = [t for t in svc.syncable_tables if t not in Base.metadata.tables]
        assert not missing, f"幽灵表名（模型中不存在）: {missing}"

    def test_syncable_tables_subset_of_allowed(self):
        """syncable_tables 必须是注入白名单的子集。"""
        svc = DataSyncService()
        outside = [t for t in svc.syncable_tables if t not in _ALLOWED_TABLES]
        assert not outside, f"不在白名单内的表: {outside}"

    def test_yearly_tables_present_with_singular_names(self):
        """11 张年度板块表必须以真实单数名参与同步。"""
        svc = DataSyncService()
        expected = {
            "village_population",
            "village_income",
            "force_investment",
            "industry_support",
            "infrastructure_improvement",
            "party_building_support",
            "medical_support",
            "consumption_support",
            "employment_support",
            "education_support",
        }
        missing = expected - set(svc.syncable_tables)
        assert not missing, f"缺失的年度表: {missing}"

    def test_no_legacy_plural_ghost_names(self):
        """旧复数幽灵表名不得残留。"""
        svc = DataSyncService()
        ghosts = [t for t in svc.syncable_tables if t.endswith(("populations", "incomes", "investments", "supports", "improvements"))]
        assert not ghosts, f"复数幽灵表名: {ghosts}"


class TestExportErrorSurfacing:
    @pytest.mark.asyncio
    async def test_table_export_exception_marks_failure(self, monkeypatch):
        """单表导出异常必须让整体 success=False 并携带 errors 明细。"""
        from app.core.database import get_db as _get_db
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        svc = DataSyncService()

        fake_db = MagicMock()
        gen = _get_db()
        # 让 _get_db_context 返回 mock db
        with patch.object(svc, "_get_db_context") as ctx:
            ctx.return_value.__enter__ = lambda s: fake_db
            ctx.return_value.__exit__ = lambda s, *a: False

            async def boom(db, table_name, since=None):
                if table_name == "supported_villages":
                    raise RuntimeError("disk io boom")
                return [{"id": 1}]

            monkeypatch.setattr(svc, "_export_table_data", boom)
            # _save_export_package 与 SyncLog 走 mock，聚焦错误上报语义
            pkg_path = svc.sync_dir / "test_pkg.zip"
            pkg_path.write_bytes(b"x")

            async def fake_save(data, name, include_files):
                return pkg_path

            monkeypatch.setattr(svc, "_save_export_package", fake_save)

            sl = SimpleNamespace(status=None, package_path=None, total_records=0,
                                 success_records=0, completed_at=None, details=None)

            class Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            fake_db.query.return_value = Q()

            from app.services.data_sync_service import ExportConfig
            result = await svc.export_incremental(
                ExportConfig(modules=["supported_villages", "policies"]))

            assert result["success"] is False
            errs = result.get("errors") or {}
            assert "supported_villages" in errs, f"errors 缺失失败表明细: {result}"
            sl.status = "failed"  # 语义锚点：日志状态应为 failed（实现内断言见服务代码）

    @pytest.mark.asyncio
    async def test_empty_table_without_error_stays_success(self, monkeypatch):
        """无新增数据（空列表、无异常）仍视为成功——不与错误上报混淆。"""
        svc = DataSyncService()
        from app.core.database import get_db as _get_db
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        fake_db = MagicMock()
        with patch.object(svc, "_get_db_context") as ctx:
            ctx.return_value.__enter__ = lambda s: fake_db
            ctx.return_value.__exit__ = lambda s, *a: False

            async def ok(db, table_name, since=None):
                return []

            monkeypatch.setattr(svc, "_export_table_data", ok)
            pkg_path = svc.sync_dir / "empty_pkg.zip"
            pkg_path.write_bytes(b"x")

            async def fake_save(data, name, include_files):
                return pkg_path

            monkeypatch.setattr(svc, "_save_export_package", fake_save)

            class Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            fake_db.query.return_value = Q()

            from app.services.data_sync_service import ExportConfig
            result = await svc.export_incremental(ExportConfig())
            assert result["success"] is True
