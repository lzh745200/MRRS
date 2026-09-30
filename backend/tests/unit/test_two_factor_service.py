import pytest
from unittest.mock import MagicMock, patch


class TestGenerateSecret:
    def test_generates_base32(self):
        from app.services.two_factor_service import TwoFactorService
        secret = TwoFactorService.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) >= 16

    def test_secrets_are_different(self):
        from app.services.two_factor_service import TwoFactorService
        s1 = TwoFactorService.generate_secret()
        s2 = TwoFactorService.generate_secret()
        assert s1 != s2


class TestGenerateBackupCodes:
    def test_default_count(self):
        from app.services.two_factor_service import TwoFactorService
        codes = TwoFactorService.generate_backup_codes()
        assert len(codes) == 10

    def test_custom_count(self):
        from app.services.two_factor_service import TwoFactorService
        codes = TwoFactorService.generate_backup_codes(5)
        assert len(codes) == 5

    def test_all_numeric(self):
        from app.services.two_factor_service import TwoFactorService
        codes = TwoFactorService.generate_backup_codes()
        for c in codes:
            assert c.isdigit()
            assert len(c) == 8


class TestGenerateQrCode:
    def test_generates_data_url(self):
        from app.services.two_factor_service import TwoFactorService

        mock_qrcode_module = MagicMock()
        mock_qr = MagicMock()
        mock_qrcode_module.QRCode.return_value = mock_qr
        mock_img = MagicMock()
        mock_qr.make_image.return_value = mock_img
        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = b"image_data"

        # qrcode 在服务层为方法内懒加载；用 sys.modules 注入假模块，
        # 使测试完全不触发真实 qrcode 导入（该包在 AV 环境下导入极慢）
        with patch.dict("sys.modules", {"qrcode": mock_qrcode_module}):
            with patch("app.services.two_factor_service.pyotp.TOTP") as mock_totp:
                mock_totp_instance = MagicMock()
                mock_totp.return_value = mock_totp_instance
                mock_totp_instance.provisioning_uri.return_value = "otpauth://totp/..."
                with patch("app.services.two_factor_service.BytesIO", return_value=mock_buffer):
                    with patch("app.services.two_factor_service.b64encode", return_value=b"base64data"):
                        result = TwoFactorService.generate_qr_code("secret", "user@test.com")
                        assert result == "data:image/png;base64,base64data"


class TestVerifyTotp:
    @patch("app.services.two_factor_service.pyotp.TOTP")
    def test_valid_token(self, mock_totp):
        from app.services.two_factor_service import TwoFactorService
        mock_totp_instance = MagicMock()
        mock_totp.return_value = mock_totp_instance
        mock_totp_instance.verify.return_value = True
        assert TwoFactorService.verify_totp("secret", "123456") is True

    @patch("app.services.two_factor_service.pyotp.TOTP")
    def test_invalid_token(self, mock_totp):
        from app.services.two_factor_service import TwoFactorService
        mock_totp_instance = MagicMock()
        mock_totp.return_value = mock_totp_instance
        mock_totp_instance.verify.return_value = False
        assert TwoFactorService.verify_totp("secret", "000000") is False

    @patch("app.services.two_factor_service.pyotp.TOTP")
    def test_exception_returns_false(self, mock_totp):
        from app.services.two_factor_service import TwoFactorService
        mock_totp.side_effect = Exception("totp error")
        assert TwoFactorService.verify_totp("secret", "123456") is False


class TestEnableTwoFactor:
    @patch("app.services.two_factor_service.TwoFactorService.generate_secret")
    @patch("app.services.two_factor_service.TwoFactorService.generate_backup_codes")
    @patch("app.services.two_factor_service.encrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.generate_qr_code")
    def test_already_enabled_raises(self, mock_qr, mock_encrypt, mock_codes, mock_secret):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        existing = MagicMock()
        existing.enabled = True
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        user = MagicMock()
        user.id = 1
        user.email = "test@test.com"
        with pytest.raises(ValueError, match="已启用"):
            TwoFactorService.enable_two_factor(mock_db, user)

    @patch("app.services.two_factor_service.TwoFactorService.generate_secret")
    @patch("app.services.two_factor_service.TwoFactorService.generate_backup_codes")
    @patch("app.services.two_factor_service.encrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.generate_qr_code")
    def test_new_record(self, mock_qr, mock_encrypt, mock_codes, mock_secret):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_secret.return_value = "new_secret"
        mock_codes.return_value = ["12345678"]
        mock_encrypt.return_value = "encrypted"
        mock_qr.return_value = "data:image/png;base64,xxx"
        user = MagicMock()
        user.id = 1
        user.email = "test@test.com"
        result = TwoFactorService.enable_two_factor(mock_db, user)
        assert result["secret"] == "new_secret"
        assert result["backup_codes"] == ["12345678"]
        mock_db.add.assert_called_once()

    @patch("app.services.two_factor_service.TwoFactorService.generate_secret")
    @patch("app.services.two_factor_service.TwoFactorService.generate_backup_codes")
    @patch("app.services.two_factor_service.encrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.generate_qr_code")
    def test_existing_not_enabled_update(self, mock_qr, mock_encrypt, mock_codes, mock_secret):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        existing = MagicMock()
        existing.enabled = False
        existing.secret_key = "old"
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        mock_secret.return_value = "new_secret"
        mock_codes.return_value = ["87654321"]
        mock_encrypt.return_value = "new_encrypted"
        mock_qr.return_value = "data:image/png;base64,yyy"
        user = MagicMock()
        user.id = 1
        user.email = "test@test.com"
        result = TwoFactorService.enable_two_factor(mock_db, user)
        assert result["secret"] == "new_secret"
        assert existing.secret_key == "new_encrypted"
        # 2026-09-30 深审修复：恢复码改为哈希落库（原断言 existing.backup_codes == ["87654321"]
        # 固化了"明文存储"这一缺陷行为），明文只随响应返回。
        assert len(existing.backup_codes) == 1
        assert existing.backup_codes[0] != "87654321"
        assert TwoFactorService.is_hashed_backup_code(existing.backup_codes[0])
        assert TwoFactorService._verify_backup_code("87654321", existing.backup_codes[0]) is True
        assert result["backup_codes"] == ["87654321"]
        assert existing.enabled is False
        mock_db.add.assert_not_called()


class TestVerifyAndEnable:
    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_no_config_raises(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        user = MagicMock()
        user.id = 1
        with pytest.raises(ValueError, match="未找到"):
            TwoFactorService.verify_and_enable(mock_db, user, "123456")

    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_valid_token_enables(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        tf.secret_key = "encrypted"
        tf.enabled = False
        tf.verified_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        mock_decrypt.return_value = "decrypted_secret"
        mock_verify.return_value = True
        user = MagicMock()
        user.id = 1
        result = TwoFactorService.verify_and_enable(mock_db, user, "123456")
        assert result is True
        assert tf.enabled is True
        assert tf.verified_at is not None
        mock_db.commit.assert_called_once()

    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_invalid_token(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        tf.secret_key = "encrypted"
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        mock_decrypt.return_value = "decrypted_secret"
        mock_verify.return_value = False
        user = MagicMock()
        user.id = 1
        result = TwoFactorService.verify_and_enable(mock_db, user, "000000")
        assert result is False


class TestVerifyLogin:
    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_no_two_factor(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        user = MagicMock()
        user.id = 1
        result = TwoFactorService.verify_login(mock_db, user, "123456")
        assert result is False

    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_totp_success(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        tf.secret_key = "encrypted"
        tf.backup_codes = ["11111111", "22222222"]
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        mock_decrypt.return_value = "decrypted"
        mock_verify.return_value = True
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        result = TwoFactorService.verify_login(mock_db, user, "123456")
        assert result is True

    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_backup_code_success(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        tf.secret_key = "encrypted"
        tf.backup_codes = ["11111111", "22222222"]
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        mock_decrypt.return_value = "decrypted"
        mock_verify.return_value = False
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        result = TwoFactorService.verify_login(mock_db, user, "11111111")
        assert result is True
        assert "11111111" not in tf.backup_codes

    @patch("app.services.two_factor_service.decrypt_field")
    @patch("app.services.two_factor_service.TwoFactorService.verify_totp")
    def test_both_fail(self, mock_verify, mock_decrypt):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        tf.secret_key = "encrypted"
        tf.backup_codes = []
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        mock_decrypt.return_value = "decrypted"
        mock_verify.return_value = False
        user = MagicMock()
        user.id = 1
        result = TwoFactorService.verify_login(mock_db, user, "000000")
        assert result is False


class TestDisableTwoFactor:
    def test_disable_existing(self):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        TwoFactorService.disable_two_factor(mock_db, user)
        mock_db.delete.assert_called_once_with(tf)
        mock_db.commit.assert_called_once()

    def test_disable_not_existing(self):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        user = MagicMock()
        user.id = 1
        TwoFactorService.disable_two_factor(mock_db, user)
        mock_db.delete.assert_not_called()


class TestIsEnabled:
    def test_enabled(self):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        tf = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = tf
        user = MagicMock()
        user.id = 1
        assert TwoFactorService.is_enabled(mock_db, user) is True

    def test_disabled(self):
        from app.services.two_factor_service import TwoFactorService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        user = MagicMock()
        user.id = 1
        assert TwoFactorService.is_enabled(mock_db, user) is False
