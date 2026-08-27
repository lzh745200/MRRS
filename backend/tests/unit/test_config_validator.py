from unittest.mock import Mock, patch


# =========== validate_config ===========

class TestValidateConfig:
    def test_pass_settings_directly(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert is_valid is True
        assert len(warnings) == 0

    def test_settings_is_none_uses_global(self):
        from app.core.config_validator import validate_config
        from app.core.config import settings as real_settings
        real_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        real_settings.DATABASE_URL = "sqlite:///./test.db"
        real_settings.PORT = 8000
        real_settings.CORS_ORIGINS = "http://localhost:8000"
        real_settings.MAX_FILE_SIZE = 52428800
        real_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=None)
        assert is_valid is True

    def test_settings_import_failure(self):
        from app.core.config_validator import validate_config
        import sys
        saved = {}
        for key in list(sys.modules.keys()):
            if 'app.core.config' in key:
                saved[key] = sys.modules.pop(key)
        try:
            import builtins
            real_import = builtins.__import__

            def raise_import(name, *args, **kwargs):
                if name == 'app.core.config':
                    raise ImportError("mock")
                return real_import(name, *args, **kwargs)
            with patch.object(builtins, '__import__', side_effect=raise_import):
                is_valid, warnings = validate_config()
                assert is_valid is False
        finally:
            sys.modules.update(saved)

    def test_secret_key_not_set(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = ""
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("SECRET_KEY" in w for w in warnings)
        assert is_valid is False

    def test_secret_key_too_short(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "short"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("过短" in w for w in warnings)
        assert is_valid is True

    def test_secret_key_absent_attr(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock(spec=[])
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("SECRET_KEY" in w for w in warnings)

    def test_database_url_not_set(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = ""
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("DATABASE_URL" in w for w in warnings)

    def test_database_url_windows_backslash(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///C:\\Users\\test\\db.sqlite"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        with patch("sys.platform", "win32"):
            is_valid, warnings = validate_config(settings=mock_settings)
            assert any("反斜杠" in w for w in warnings)
            assert is_valid is True

    def test_database_url_windows_forward_slash_no_warning(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///C:/Users/test/db.sqlite"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        with patch("sys.platform", "win32"):
            is_valid, warnings = validate_config(settings=mock_settings)
            assert not any("反斜杠" in w for w in warnings)

    def test_database_url_non_sqlite_no_warning(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "postgresql://localhost/db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert not any("DATABASE_URL" in w for w in warnings)

    def test_port_out_of_range_low(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 80
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("PORT" in w for w in warnings)

    def test_port_out_of_range_high(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 99999
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("PORT" in w for w in warnings)

    def test_cors_origins_not_set(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = ""
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("CORS_ORIGINS" in w for w in warnings)

    def test_max_file_size_invalid(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 0
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("MAX_FILE_SIZE" in w for w in warnings)

    def test_log_level_invalid(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "TRACE"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("LOG_LEVEL" in w for w in warnings)

    def test_log_level_valid_accounts_for_case(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "warning"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert not any("LOG_LEVEL" in w for w in warnings)

    def test_all_issues_at_once(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = ""
        mock_settings.DATABASE_URL = ""
        mock_settings.PORT = 80
        mock_settings.CORS_ORIGINS = ""
        mock_settings.MAX_FILE_SIZE = -1
        mock_settings.LOG_LEVEL = "TRACE"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert is_valid is False
        assert len(warnings) >= 5

    def test_port_default_8000_when_attr_missing(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock(spec=[])
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = 52428800
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        # PORT defaults to 8000 which is valid, so no warning
        assert not any("PORT" in w for w in warnings)

    def test_max_file_size_negative(self):
        from app.core.config_validator import validate_config
        mock_settings = Mock()
        mock_settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
        mock_settings.DATABASE_URL = "sqlite:///./test.db"
        mock_settings.PORT = 8000
        mock_settings.CORS_ORIGINS = "http://localhost:8000"
        mock_settings.MAX_FILE_SIZE = -1
        mock_settings.LOG_LEVEL = "INFO"
        is_valid, warnings = validate_config(settings=mock_settings)
        assert any("MAX_FILE_SIZE" in w for w in warnings)


# =========== check_required_dirs ===========

class TestCheckRequiredDirs:
    def test_pass_settings_directly_all_valid(self):
        from app.core.config_validator import check_required_dirs
        mock_settings = Mock()
        mock_settings.CACHE_DIR = "C:/tmp/cache"
        mock_settings.UPLOAD_DIR = "C:/tmp/uploads"
        mock_settings.LOG_DIR = "C:/tmp/logs"
        mock_settings.EXPORT_DIR = "C:/tmp/exports"
        with patch("app.core.config_validator.os.makedirs"):
            result = check_required_dirs(settings=mock_settings)
            assert result == []

    def test_settings_is_none_uses_global(self):
        from app.core.config_validator import check_required_dirs
        from app.core.config import settings as real_settings
        real_settings.CACHE_DIR = "C:/tmp/cache"
        real_settings.UPLOAD_DIR = "C:/tmp/uploads"
        real_settings.LOG_DIR = "C:/tmp/logs"
        real_settings.EXPORT_DIR = "C:/tmp/exports"
        with patch("app.core.config_validator.os.makedirs"):
            result = check_required_dirs(settings=None)
            assert result == []

    def test_settings_import_failure(self):
        from app.core.config_validator import check_required_dirs
        import sys
        saved = {}
        for key in list(sys.modules.keys()):
            if 'app.core.config' in key:
                saved[key] = sys.modules.pop(key)
        try:
            import builtins
            real_import = builtins.__import__

            def raise_import(name, *args, **kwargs):
                if name == 'app.core.config':
                    raise ImportError("mock")
                return real_import(name, *args, **kwargs)
            with patch.object(builtins, '__import__', side_effect=raise_import):
                result = check_required_dirs()
                assert any("无法加载配置" in r for r in result)
        finally:
            sys.modules.update(saved)

    def test_path_not_absolute(self):
        from app.core.config_validator import check_required_dirs
        mock_settings = Mock()
        mock_settings.CACHE_DIR = "relative/cache"
        mock_settings.UPLOAD_DIR = "C:/tmp/uploads"
        mock_settings.LOG_DIR = "C:/tmp/logs"
        mock_settings.EXPORT_DIR = "C:/tmp/exports"
        with patch("app.core.config_validator.os.makedirs") as mock_mkdir:
            result = check_required_dirs(settings=mock_settings)
            assert any("不是绝对路径" in r for r in result)
            assert len(result) == 1
            assert mock_mkdir.call_count == 3

    def test_path_empty_skipped(self):
        from app.core.config_validator import check_required_dirs
        mock_settings = Mock()
        mock_settings.CACHE_DIR = ""
        mock_settings.UPLOAD_DIR = ""
        mock_settings.LOG_DIR = ""
        mock_settings.EXPORT_DIR = ""
        with patch("app.core.config_validator.os.makedirs") as mock_mkdir:
            result = check_required_dirs(settings=mock_settings)
            assert result == []
            mock_mkdir.assert_not_called()

    def test_makedirs_os_error(self):
        from app.core.config_validator import check_required_dirs
        mock_settings = Mock()
        mock_settings.CACHE_DIR = "C:/tmp/cache"
        mock_settings.UPLOAD_DIR = "C:/tmp/uploads"
        mock_settings.LOG_DIR = "C:/tmp/logs"
        mock_settings.EXPORT_DIR = "C:/tmp/exports"
        with patch("app.core.config_validator.os.makedirs", side_effect=OSError("permission denied")):
            result = check_required_dirs(settings=mock_settings)
            assert any("无法创建" in r for r in result)
            assert len(result) == 4

    def test_all_dirs_created_successfully(self):
        from app.core.config_validator import check_required_dirs
        mock_settings = Mock()
        mock_settings.CACHE_DIR = "C:/tmp/cache"
        mock_settings.UPLOAD_DIR = "C:/tmp/uploads"
        mock_settings.LOG_DIR = "C:/tmp/logs"
        mock_settings.EXPORT_DIR = "C:/tmp/exports"
        with patch("app.core.config_validator.os.makedirs") as mock_mkdir:
            result = check_required_dirs(settings=mock_settings)
            assert result == []
            assert mock_mkdir.call_count == 4


# ProductionSettings 死类（Backward-compat stub，无任何引用）已随死代码清理删除，
# 其配套用例一并移除（2026-08-27）。


# =========== REQUIRED_ENV_VARS ===========

class TestRequiredEnvVars:
    def test_has_secret_key(self):
        from app.core.config_validator import REQUIRED_ENV_VARS
        assert "SECRET_KEY" in REQUIRED_ENV_VARS
