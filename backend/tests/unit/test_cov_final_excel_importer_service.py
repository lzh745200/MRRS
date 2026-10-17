"""补齐 app.services.excel_importer_service 覆盖率缺口。

目标行：426 —— _import_full_mode 存在 current_user 时，删除范围经
filter_by_data_scope 限定（数据权限）。
"""

from unittest.mock import MagicMock, patch

from app.services.excel_importer_service import ExcelImporterService


class TestImportFullModeDataScope:
    def test_soft_delete_scoped_to_current_user(self):
        """全量覆盖导入的「清空」必须是**软删除**且经数据域过滤（W18-D2 订正）。

        旧断言 `scoped_query.delete.assert_called_once()` 锁定的是**缺陷本身**：
        物理 DELETE 会连回收站行一起抹掉，并因 projects/funds 的 ON DELETE CASCADE
        把项目与经费一并物理删除（实证 1村/1项目/1经费 → 项目0/经费0）。
        新契约：只把当前可见行的 is_active 置 False，数据可恢复、不触发级联。
        """
        db = MagicMock()
        user = MagicMock()
        svc = ExcelImporterService(db, current_user=user)
        result = MagicMock()
        result.failed_rows = 0

        with patch("app.services.excel_importer_service.scoped_filter") as mock_scope:
            scoped_query = db.query.return_value
            mock_scope.return_value = scoped_query
            out = svc._import_full_mode([], result, MagicMock())

        mock_scope.assert_called_once()
        # 不再物理删除（含链式调用后的任何子 mock 都不应出现 delete）
        assert not scoped_query.delete.called
        # 改为软删除：在 filter(is_active is True) 之后的查询上执行 update
        filtered = scoped_query.filter.return_value
        filtered.update.assert_called_once()
        update_payload = filtered.update.call_args[0][0]
        assert list(update_payload.values()) == [False]
        assert out is result
