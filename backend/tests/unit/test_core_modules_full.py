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

    def test_generate_password_retries_until_complex(self, monkeypatch):
        """首次抽到的密码不满足复杂度要求时必须回绕重抽，直到满足为止。

        守护 `app/core/security.py` 的 `182->178`（`while True` 的回绕弧）。
        该分支此前**只靠随机命中**：一次抽到"无大写/无数字/无特殊字符"的概率虽低
        但非零，于是 `.coveragerc` 的 `fail_under=100` 分支门禁变成不确定的 ——
        CI 与本地串行的结论会不一致（2026-10-17 实测：CI 100.00%，本地 99.99%）。
        这里用可控的 `secrets.choice` 替身**确定性地**走一遍回绕路径。
        """
        import app.core.security as sec

        calls = {"n": 0}

        def fake_choice(seq):
            i = calls["n"]
            calls["n"] += 1
            if i < 12:          # 第 1 轮（默认 length=12）全 'a'：缺大写/数字/特殊字符
                return "a"
            return "Aa1!"[(i - 12) % 4]   # 第 2 轮起循环四类字符，必然满足全部要求

        monkeypatch.setattr(sec.secrets, "choice", fake_choice)

        password = sec.generate_password()

        # 必须真的回绕过：第 2 轮至少抽了一次才返回
        assert calls["n"] >= 13, "未发生回绕，该用例没有守护到 182->178"
        assert len(password) == 12
        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(not c.isalnum() for c in password)

    def test_generate_password_respects_min_length(self):
        """length < 8 时被抬到下限 8（不得生成过短密码）。"""
        from app.core.security import generate_password
        assert len(generate_password(length=4)) == 8

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
