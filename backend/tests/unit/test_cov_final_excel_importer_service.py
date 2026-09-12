"""补齐 app.services.excel_importer_service 覆盖率缺口。

目标行：426 —— _import_full_mode 存在 current_user 时，删除范围经
filter_by_data_scope 限定（数据权限）。
"""

from unittest.mock import MagicMock, patch

from app.services.excel_importer_service import ExcelImporterService


class TestImportFullModeDataScope:
    def test_delete_scoped_to_current_user(self):
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
        scoped_query.delete.assert_called_once_with(synchronize_session=False)
        assert out is result
