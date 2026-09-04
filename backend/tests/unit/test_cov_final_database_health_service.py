"""补齐 app.services.database_health_service 覆盖率缺口。

目标行：
- 69：sqlite:/// 绝对路径直接返回
- 76-78：读取配置异常 → 回退默认路径
"""

from unittest.mock import patch

from app.services.database_health_service import DatabaseHealthService


class _BrokenSettings:
    @property
    def DATABASE_URL(self):
        raise RuntimeError("cfg broken")


class TestGetDbPath:
    def test_absolute_sqlite_path_returned_as_is(self, tmp_path):
        svc = DatabaseHealthService()
        abs_db = tmp_path / "health.db"
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DATABASE_URL = f"sqlite:///{abs_db.as_posix()}"
            result = svc._get_db_path()
        assert result == abs_db

    def test_config_exception_falls_back_to_default(self):
        svc = DatabaseHealthService()
        with patch("app.core.config.settings", _BrokenSettings()):
            result = svc._get_db_path()
        assert result == svc.base_dir / "data" / "rural_revitalization.db"
