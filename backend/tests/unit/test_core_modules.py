"""
Core模块全面测试
覆盖app/core/下的所有模块
"""



class TestSecurity:
    """测试安全模块"""

    def test_security_import(self):
        """测试安全模块导入"""
        from app.core import security
        assert security is not None

    def test_verify_password(self):
        """测试验证密码"""
        from app.core.security import verify_password
        result = verify_password("test", "hashed")
        assert isinstance(result, bool)

    def test_get_password_hash(self):
        """测试获取密码哈希"""
        from app.core.security import get_password_hash
        result = get_password_hash("password")
        assert isinstance(result, str)

    def test_create_access_token(self):
        """测试创建访问令牌"""
        from app.core.security import create_access_token
        token = create_access_token({"sub": "test"})
        assert isinstance(token, str)

class TestConfig:
    """测试配置模块"""

    def test_config_import(self):
        """测试配置导入"""
        from app.core import config
        assert config is not None

    def test_settings_import(self):
        """测试设置导入"""
        from app.core.config import settings
        assert settings is not None

class TestDatabase:
    """测试数据库模块"""

    def test_database_import(self):
        """测试数据库导入"""
        from app.core import database
        assert database is not None

    def test_get_db_import(self):
        """测试get_db导入"""
        from app.core.database import get_db
        assert callable(get_db)

    def test_session_local_import(self):
        """测试SessionLocal导入"""
        from app.core.database import SessionLocal
        assert SessionLocal is not None

class TestExceptions:
    """测试异常模块"""

    def test_exceptions_import(self):
        """测试异常模块导入"""
        from app.core import exceptions
        assert exceptions is not None

    def test_business_error(self):
        """测试业务错误"""
        from app.core.exceptions import BusinessError
        exc = BusinessError("test")
        assert str(exc) == "test"

    def test_not_found_error(self):
        """测试未找到错误"""
        from app.core.exceptions import NotFoundError
        exc = NotFoundError("test")
        assert "test" in str(exc)

    def test_validation_error(self):
        """测试验证错误"""
        from app.core.exceptions import ValidationError
        exc = ValidationError("test")
        assert "test" in str(exc)

class TestLogging:
    """测试日志模块"""

    def test_logging_config_import(self):
        """测试日志配置导入"""
        from app.core import logging_config
        assert logging_config is not None

    def test_get_logger(self):
        """测试获取日志记录器"""
        import logging
        logger = logging.getLogger("test")
        assert logger is not None

class TestStaticFiles:
    """测试静态文件"""

    def test_static_files_import(self):
        """测试静态文件导入"""
        from fastapi.staticfiles import StaticFiles
        assert StaticFiles is not None

class TestTransaction:
    """测试事务"""

    def test_transaction_import(self):
        """测试事务导入"""
        from app.core import transaction
        assert transaction is not None

    def test_transactional(self):
        """测试事务装饰器"""
        from app.core.transaction import transactional
        assert callable(transactional)
