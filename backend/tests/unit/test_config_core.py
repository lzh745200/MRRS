"""
app/core/config.py 单元测试 — 目标 100% 行覆盖。

测试内容：
- 默认路径辅助函数：_get_default_data_dir / _get_default_database_url /
  _get_default_cache_dir / _get_default_uploads_dir / _get_default_exports_dir
- Settings 计算属性：CORS_ALLOWED_ORIGINS / cors_origins_list /
  CORS_ALLOWED_METHODS / cors_allow_methods_list /
  CORS_ALLOWED_HEADERS / cors_allow_headers_list / allowed_file_types_list
- model_post_init 分支：空 DATABASE_URL / 生产环境 DB_ECHO 强制关闭 /
  sys.frozen 日志路径 / 相对路径 DATABASE_URL 转绝对路径
- _load_encrypted_secrets：文件不存在 / 全部解密成功 / 单个解密失败 / 外层异常
"""
import json
import sys
from unittest.mock import MagicMock


from app.core.config import (
    Settings,
    _get_default_cache_dir,
    _get_default_data_dir,
    _get_default_database_url,
    _get_default_exports_dir,
    _get_default_uploads_dir,
)


# ---------------------------------------------------------------------------
# 默认路径辅助函数
# ---------------------------------------------------------------------------
class TestDefaultPathHelpers:
    """测试动态计算默认路径的辅助函数（覆盖函数体）。"""

    def test_get_default_data_dir(self):
        result = _get_default_data_dir()
        assert isinstance(result, str)
        assert result.endswith("/data")
        assert "\\" not in result

    def test_get_default_database_url(self):
        result = _get_default_database_url()
        assert result.startswith("sqlite:///")
        assert result.endswith(".db")
        assert "\\" not in result

    def test_get_default_cache_dir(self):
        result = _get_default_cache_dir()
        assert isinstance(result, str)
        assert "/" in result
        assert "\\" not in result

    def test_get_default_uploads_dir(self):
        result = _get_default_uploads_dir()
        assert isinstance(result, str)
        assert "/" in result
        assert "\\" not in result

    def test_get_default_exports_dir(self):
        result = _get_default_exports_dir()
        assert isinstance(result, str)
        assert "/" in result
        assert "\\" not in result


# ---------------------------------------------------------------------------
# Settings 计算属性
# ---------------------------------------------------------------------------
class TestSettingsProperties:
    """测试 Settings 类上的 @property 计算属性。"""

    def test_cors_origins_properties(self):
        s = Settings(CORS_ORIGINS="http://a.com, http://b.com")
        assert s.CORS_ALLOWED_ORIGINS == ["http://a.com", "http://b.com"]
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_cors_methods_properties(self):
        s = Settings(CORS_ALLOW_METHODS="get, post, put")
        assert s.CORS_ALLOWED_METHODS == ["GET", "POST", "PUT"]
        assert s.cors_allow_methods_list == ["GET", "POST", "PUT"]

    def test_cors_headers_properties(self):
        s = Settings(CORS_ALLOW_HEADERS="Content-Type, Authorization")
        assert s.CORS_ALLOWED_HEADERS == ["Content-Type", "Authorization"]
        assert s.cors_allow_headers_list == ["Content-Type", "Authorization"]

    def test_allowed_file_types_list(self):
        s = Settings(ALLOWED_FILE_TYPES="xlsx, pdf, JPG")
        assert s.allowed_file_types_list == ["xlsx", "pdf", "jpg"]


# ---------------------------------------------------------------------------
# model_post_init 分支
# ---------------------------------------------------------------------------
class TestModelPostInit:
    """测试 model_post_init 钩子的各分支。"""

    def test_empty_database_url_uses_default(self):
        """DATABASE_URL 为空时调用 _get_default_database_url() 动态计算。"""
        s = Settings(DATABASE_URL="")
        assert s.DATABASE_URL.startswith("sqlite:///")
        assert s.DATABASE_URL.endswith(".db")
        assert "\\" not in s.DATABASE_URL

    def test_relative_database_url_converted_to_absolute(self):
        """sqlite:///./xxx 形式的相对路径转为绝对路径。"""
        s = Settings(DATABASE_URL="sqlite:///./custom.db")
        assert s.DATABASE_URL.startswith("sqlite:///")
        # 不再包含相对路径标记
        assert "./" not in s.DATABASE_URL
        assert s.DATABASE_URL.endswith("custom.db")

    def test_production_db_echo_forced_off(self, caplog):
        """生产环境 DB_ECHO=True 时强制关闭并记录警告。"""
        with caplog.at_level("WARNING", logger="app.core.config"):
            s = Settings(ENVIRONMENT="production", DB_ECHO=True)
        assert s.DB_ECHO is False
        assert any(
            "DB_ECHO" in r.message and "强制关闭" in r.message
            for r in caplog.records
        )

    def test_production_db_echo_already_off(self):
        """生产环境 DB_ECHO=False 时不触发警告。"""
        s = Settings(ENVIRONMENT="production", DB_ECHO=False)
        assert s.DB_ECHO is False

    def test_production_pass_code_secret_missing_warns(self, caplog):
        """生产环境未配置 PASS_CODE_SECRET → 跨机器自验证 fail-closed 告警（ADR-0004）。"""
        with caplog.at_level("WARNING", logger="app.core.config"):
            Settings(ENVIRONMENT="production", PASS_CODE_SECRET="")
        assert any(
            "PASS_CODE_SECRET" in r.message and "fail-closed" in r.message
            for r in caplog.records
        )

    def test_production_pass_code_secret_set_no_warn(self, caplog):
        """生产环境已配置 PASS_CODE_SECRET → 不触发 fail-closed 告警。"""
        with caplog.at_level("WARNING", logger="app.core.config"):
            s = Settings(ENVIRONMENT="production", PASS_CODE_SECRET="shared-secret-x")
        assert s.PASS_CODE_SECRET == "shared-secret-x"
        assert not any("PASS_CODE_SECRET 未配置" in r.message for r in caplog.records)

    def test_frozen_log_dir_uses_data_dir(self, monkeypatch):
        """sys.frozen=True 时 LOG_DIR/LOG_FILE 放到数据目录下。"""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        s = Settings()
        assert not s.LOG_DIR.startswith("./")
        assert s.LOG_DIR.endswith("/logs")
        assert s.LOG_FILE.endswith("/logs/app.log")
        assert "\\" not in s.LOG_DIR


# ---------------------------------------------------------------------------
# _load_encrypted_secrets
# ---------------------------------------------------------------------------
class TestLoadEncryptedSecrets:
    """测试加密密钥加载的各分支。"""

    def test_files_not_exist(self, tmp_path, caplog):
        """加密密钥文件不存在 → 记录警告并回退到环境变量。"""
        with caplog.at_level("WARNING", logger="app.core.config"):
            s = Settings(
                USE_ENCRYPTED_SECRETS=True,
                SECRETS_FILE_PATH=str(tmp_path / "nonexistent.json"),
                MASTER_KEY_PATH=str(tmp_path / "nonexistent.key"),
            )
        assert any("加密密钥文件不存在" in r.message for r in caplog.records)

    def test_decrypt_all_keys_success(self, monkeypatch, tmp_path, caplog):
        """四种密钥分支全部进入：三个模型字段成功设置，DB_ENCRYPTION_KEY
        因非模型字段在 pydantic v2 下 setattr 报错（源码行为，被内层 except 捕获）。"""
        master_key_file = tmp_path / "master.key"
        master_key_file.write_text("master-key-base64-string", encoding="utf-8")

        secrets_file = tmp_path / "encrypted.json"
        secrets_file.write_text(
            json.dumps({
                "SECRET_KEY": "enc-sk",
                "CSRF_SECRET_KEY": "enc-csrf",
                "SMTP_PASSWORD": "enc-smtp",
                "DB_ENCRYPTION_KEY": "enc-dbkey",
            }),
            encoding="utf-8",
        )

        decrypt_map = {
            b"enc-sk": b"decrypted-secret",
            b"enc-csrf": b"decrypted-csrf",
            b"enc-smtp": b"decrypted-smtp-pass",
            b"enc-dbkey": b"decrypted-db-key",
        }
        mock_encryptor = MagicMock()
        mock_encryptor.decrypt_data.side_effect = lambda data: decrypt_map[data]
        mock_class = MagicMock()
        mock_class.from_key_string.return_value = mock_encryptor

        monkeypatch.setattr("app.utils.encryption.DataPackageEncryption", mock_class)

        with caplog.at_level("ERROR", logger="app.core.config"):
            s = Settings(
                USE_ENCRYPTED_SECRETS=True,
                SECRETS_FILE_PATH=str(secrets_file),
                MASTER_KEY_PATH=str(master_key_file),
            )

        # 三个模型字段成功解密并设置
        assert s.SECRET_KEY == "decrypted-secret"
        assert s.CSRF_SECRET_KEY == "decrypted-csrf"
        assert s.SMTP_PASSWORD == "decrypted-smtp-pass"
        # DB_ENCRYPTION_KEY 非模型字段，setattr 失败被内层 except 捕获并记录
        assert any(
            "DB_ENCRYPTION_KEY" in r.message and "失败" in r.message
            for r in caplog.records
        )

    def test_decrypt_failure_for_one_key(self, monkeypatch, tmp_path, caplog):
        """单个密钥解密失败 → 记录错误，其他密钥仍正常设置。"""
        master_key_file = tmp_path / "master.key"
        master_key_file.write_text("master-key", encoding="utf-8")

        secrets_file = tmp_path / "encrypted.json"
        secrets_file.write_text(
            json.dumps({
                "SECRET_KEY": "good",
                "SMTP_PASSWORD": "bad",
            }),
            encoding="utf-8",
        )

        def mock_decrypt(data):
            if data == b"bad":
                raise RuntimeError("decrypt failed")
            return b"ok-value"

        mock_encryptor = MagicMock()
        mock_encryptor.decrypt_data.side_effect = mock_decrypt
        mock_class = MagicMock()
        mock_class.from_key_string.return_value = mock_encryptor

        monkeypatch.setattr("app.utils.encryption.DataPackageEncryption", mock_class)

        with caplog.at_level("ERROR", logger="app.core.config"):
            s = Settings(
                USE_ENCRYPTED_SECRETS=True,
                SECRETS_FILE_PATH=str(secrets_file),
                MASTER_KEY_PATH=str(master_key_file),
            )

        # SECRET_KEY 成功解密
        assert s.SECRET_KEY == "ok-value"
        # SMTP_PASSWORD 解密失败，错误被记录
        assert any(
            "解密密钥" in r.message and "失败" in r.message
            for r in caplog.records
        )

    def test_outer_exception_invalid_json(self, tmp_path, caplog):
        """secrets 文件 JSON 格式损坏 → 外层 except 捕获并记录错误。"""
        master_key_file = tmp_path / "master.key"
        master_key_file.write_text("master-key", encoding="utf-8")

        secrets_file = tmp_path / "encrypted.json"
        secrets_file.write_text("NOT VALID JSON {{{", encoding="utf-8")

        with caplog.at_level("ERROR", logger="app.core.config"):
            s = Settings(
                USE_ENCRYPTED_SECRETS=True,
                SECRETS_FILE_PATH=str(secrets_file),
                MASTER_KEY_PATH=str(master_key_file),
            )

        assert any("加载加密密钥失败" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Settings 默认值验证
# ---------------------------------------------------------------------------
class TestSettingsDefaults:
    """验证关键字段默认值（确保导入时默认值未被破坏）。"""

    def test_key_defaults(self, monkeypatch):
        # mock_settings 会注入 CSRF_ENABLED=false 等环境变量，删除后验证真实默认值
        monkeypatch.delenv("CSRF_ENABLED", raising=False)
        s = Settings()
        assert s.PROJECT_NAME == "帮扶管理信息系统"
        assert s.ALGORITHM == "HS256"
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 480
        assert s.BCRYPT_ROUNDS == 12
        assert s.CSRF_ENABLED is True
        assert s.RATE_LIMIT_ENABLED is True
        assert s.HEALTH_CHECK_ENABLED is True
