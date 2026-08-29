"""
核心模块全面测试 — Base import path changed
"""



class TestCoreConfig:
    """测试核心配置"""

    def test_config_import(self):
        """测试配置导入"""
        from app.core import config
        assert config is not None

    def test_settings_singleton(self):
        """测试设置单例"""
        from app.core.config import settings
        assert settings is not None

    def test_database_url(self):
        """测试数据库URL"""
        from app.core.config import settings
        assert hasattr(settings, 'DATABASE_URL')

    def test_secret_key(self):
        """测试密钥"""
        from app.core.config import settings
        assert hasattr(settings, 'SECRET_KEY')

class TestCoreDatabase:
    """测试核心数据库"""

    def test_database_import(self):
        """测试数据库导入"""
        from app.core import database
        assert database is not None

    def test_engine_exists(self):
        """测试引擎存在"""
        from app.core.database import engine
        assert engine is not None

    def test_session_local(self):
        """测试会话本地"""
        from app.core.database import SessionLocal
        assert SessionLocal is not None

    def test_base_model(self):
        """测试基础模型"""
        from app.models.base import Base
        assert Base is not None

class TestCoreSecurity:
    """测试核心安全"""

    def test_security_import(self):
        """测试安全导入"""
        from app.core import security
        assert security is not None

    def test_get_password_hash(self):
        """测试获取密码哈希"""
        from app.core.security import get_password_hash
        result = get_password_hash("test123")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_verify_password(self):
        """测试验证密码"""
        from app.core.security import get_password_hash, verify_password
        hashed = get_password_hash("test123")
        assert verify_password("test123", hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_generate_password(self):
        """测试生成密码"""
        from app.core.security import generate_password
        password = generate_password()
        assert isinstance(password, str)
        assert len(password) > 0

    def test_generate_temp_password(self):
        """测试生成临时密码"""
        from app.core.security import generate_temp_password
        password = generate_temp_password()
        assert isinstance(password, str)
        assert len(password) > 0

    def test_get_client_ip(self):
        """测试获取客户端IP"""
        from app.core.security import get_client_ip
        assert callable(get_client_ip)

class TestCoreLogging:
    """测试核心日志"""

    def test_logging_import(self):
        """测试日志导入"""
        from app.core import logging_config
        assert logging_config is not None

class TestCoreExceptions:
    """测试核心异常"""

    def test_exceptions_import(self):
        """测试异常导入"""
        from app.core import exceptions
        assert exceptions is not None
