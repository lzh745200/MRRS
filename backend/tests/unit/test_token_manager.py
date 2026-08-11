"""Tests for app.core.token_manager (100% coverage)."""

from datetime import timedelta
from unittest.mock import MagicMock, patch


from app.core.token_manager import (
    TokenManager,
    _get_algorithm,
    _get_secret_key,
    _get_settings,
    _persist_revocation,
    create_token_pair,
    refresh_access_token,
    revoke_token,
    token_manager,
    validate_token,
)


# ---------------------------------------------------------------------------
# _persist_revocation
# ---------------------------------------------------------------------------


class TestPersistRevocation:
    @patch("app.core.token_blacklist.add_to_db")
    @patch("app.core.database.SessionLocal")
    def test_success(self, mock_session_local, mock_add_to_db):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        _persist_revocation("some-jti", reason="logout")

        mock_session_local.assert_called_once_with()
        mock_add_to_db.assert_called_once_with(
            "some-jti", mock_db, reason="logout",
            expires_at=None, user_id=None,
        )
        mock_db.close.assert_called_once()

    @patch("app.core.token_blacklist.add_to_db")
    @patch("app.core.database.SessionLocal")
    def test_add_to_db_raises(self, mock_session_local, mock_add_to_db):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_add_to_db.side_effect = RuntimeError("db error")

        _persist_revocation("some-jti", reason="logout")

        mock_db.close.assert_called_once()

    @patch("app.core.database.SessionLocal")
    def test_session_local_raises(self, mock_session_local):
        mock_session_local.side_effect = RuntimeError("connection error")

        _persist_revocation("some-jti", reason="logout")


# ---------------------------------------------------------------------------
# _get_settings
# ---------------------------------------------------------------------------


class TestGetSettings:
    @patch("app.core.config.settings", new_callable=MagicMock)
    def test_returns_settings(self, mock_settings):
        result = _get_settings()
        assert result is mock_settings

    def test_exception_returns_none(self):
        """_get_settings catches any exception from the import and returns None."""
        import app.core.config as config_mod
        orig = config_mod.settings
        try:
            del config_mod.settings
            result = _get_settings()
            assert result is None
        finally:
            config_mod.settings = orig


# ---------------------------------------------------------------------------
# _get_secret_key / _get_algorithm
# ---------------------------------------------------------------------------


class TestGetSecretKey:
    @patch("app.core.security.SECRET_KEY", "test-secret")
    def test_returns_secret_key(self):
        assert _get_secret_key() == "test-secret"


class TestGetAlgorithm:
    @patch("app.core.security.ALGORITHM", "HS384")
    def test_returns_algorithm(self):
        assert _get_algorithm() == "HS384"


# ---------------------------------------------------------------------------
# create_token_pair
# ---------------------------------------------------------------------------


class TestCreateTokenPair:
    @patch("app.core.token_manager._get_settings")
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.encode", side_effect=lambda p, s, algorithm=None: f"encoded.{p.get('type')}")
    def test_basic(self, mock_encode, mock_algo, mock_key, mock_settings):
        mock_settings.return_value = MagicMock(
            ACCESS_TOKEN_EXPIRE_MINUTES=30, REFRESH_TOKEN_EXPIRE_DAYS=7
        )

        result = create_token_pair("user1")

        assert result["token_type"] == "bearer"
        assert result["expires_in"] == 30 * 60
        assert result["access_token"] == "encoded.access"
        assert result["refresh_token"] == "encoded.refresh"
        assert mock_encode.call_count == 2

    @patch("app.core.token_manager._get_settings", return_value=None)
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.encode", side_effect=lambda p, s, algorithm=None: f"e.{p.get('type')}")
    def test_no_settings_fallback_defaults(self, mock_encode, mock_algo, mock_key, mock_settings):
        result = create_token_pair("user1")
        assert result["expires_in"] == 480 * 60

    @patch("app.core.token_manager._get_settings")
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.encode", side_effect=lambda p, s, algorithm=None: f"e.{p.get('type')}")
    def test_with_extra_claims(self, mock_encode, mock_algo, mock_key, mock_settings):
        mock_settings.return_value = MagicMock(
            ACCESS_TOKEN_EXPIRE_MINUTES=30, REFRESH_TOKEN_EXPIRE_DAYS=7
        )

        result = create_token_pair("user1", extra_claims={"role": "admin", "org": "unit"})

        first_payload = mock_encode.call_args_list[0][0][0]
        assert first_payload["role"] == "admin"
        assert first_payload["org"] == "unit"
        assert result["access_token"] == "e.access"

    @patch("app.core.token_manager._get_settings")
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.encode", side_effect=lambda p, s, algorithm=None: f"e.{p.get('type')}")
    def test_custom_ttl(self, mock_encode, mock_algo, mock_key, mock_settings):
        mock_settings.return_value = MagicMock(
            ACCESS_TOKEN_EXPIRE_MINUTES=30, REFRESH_TOKEN_EXPIRE_DAYS=7
        )

        result = create_token_pair("user1", access_ttl_minutes=15, refresh_ttl_days=1)

        assert result["expires_in"] == 15 * 60

    @patch("app.core.token_manager._get_settings")
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.encode", side_effect=lambda p, s, algorithm=None: f"e.{p.get('type')}")
    def test_settings_missing_attrs(self, mock_encode, mock_algo, mock_key, mock_settings):
        settings_mock = MagicMock(spec=[])
        del settings_mock.ACCESS_TOKEN_EXPIRE_MINUTES
        del settings_mock.REFRESH_TOKEN_EXPIRE_DAYS
        mock_settings.return_value = settings_mock

        result = create_token_pair("user1")
        assert result["expires_in"] == 480 * 60


# ---------------------------------------------------------------------------
# validate_token
# ---------------------------------------------------------------------------


class TestValidateToken:
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    @patch("app.core.token_blacklist.is_blacklisted", return_value=False)
    def test_valid_token(self, mock_blacklisted, mock_decode, mock_algo, mock_key):
        mock_decode.return_value = {"sub": "user1", "jti": "abc", "type": "access"}
        valid, payload, err = validate_token("some-token")
        assert valid is True
        assert payload["sub"] == "user1"
        assert err is None

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    @patch("app.core.token_blacklist.is_blacklisted", return_value=True)
    def test_blacklisted_token(self, mock_blacklisted, mock_decode, mock_algo, mock_key):
        mock_decode.return_value = {"sub": "user1", "jti": "abc", "type": "access"}
        valid, payload, err = validate_token("some-token")
        assert valid is False
        assert err == "令牌已被吊销"
        mock_blacklisted.assert_called_once_with("abc")

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    @patch("app.core.token_blacklist.is_blacklisted", return_value=False)
    def test_wrong_type(self, mock_blacklisted, mock_decode, mock_algo, mock_key):
        mock_decode.return_value = {"sub": "user1", "jti": "abc", "type": "refresh"}
        valid, payload, err = validate_token("some-token", token_type="access")
        assert valid is False
        assert "令牌类型不匹配" in err

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    @patch("app.core.token_blacklist.is_blacklisted", return_value=False)
    def test_no_type_claim(self, mock_blacklisted, mock_decode, mock_algo, mock_key):
        mock_decode.return_value = {"sub": "user1", "jti": "abc"}
        valid, payload, err = validate_token("some-token", token_type="access")
        assert valid is True
        assert payload["sub"] == "user1"
        assert err is None

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    @patch("app.core.token_blacklist.is_blacklisted", return_value=False)
    def test_no_jti_claim(self, mock_blacklisted, mock_decode, mock_algo, mock_key):
        mock_decode.return_value = {"sub": "user1", "type": "access"}
        valid, payload, err = validate_token("some-token")
        assert valid is True
        assert payload["sub"] == "user1"
        mock_blacklisted.assert_not_called()

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    def test_jwt_error(self, mock_decode, mock_algo, mock_key):
        from jwt import InvalidTokenError as JWTError

        mock_decode.side_effect = JWTError("bad sig")
        valid, payload, err = validate_token("bad-token")
        assert valid is False
        assert "令牌验证失败" in err
        assert payload is None

    def test_empty_token(self):
        valid, payload, err = validate_token("")
        assert valid is False
        assert err == "令牌为空"

        valid, payload, err = validate_token("  ")
        assert valid is False
        assert err is not None


# ---------------------------------------------------------------------------
# revoke_token
# ---------------------------------------------------------------------------


class TestRevokeToken:
    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("app.core.token_manager._persist_revocation")
    @patch("app.core.token_blacklist.add")
    @patch("jwt.decode")
    def test_success(self, mock_decode, mock_add, mock_persist, mock_algo, mock_key):
        mock_decode.return_value = {"jti": "abc123", "exp": 9999999999}
        result = revoke_token("some-token", reason="logout")
        assert result is True
        mock_add.assert_called_once()
        # expires_at is passed through from the token's exp claim
        call_kwargs = mock_persist.call_args
        assert call_kwargs[0][0] == "abc123"
        assert call_kwargs[0][1] == "logout"
        assert "expires_at" in call_kwargs[1]

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("app.core.token_manager._persist_revocation")
    @patch("app.core.token_blacklist.add")
    @patch("jwt.decode")
    def test_missing_jti(self, mock_decode, mock_add, mock_persist, mock_algo, mock_key):
        mock_decode.return_value = {"sub": "user1"}
        result = revoke_token("some-token")
        assert result is False
        mock_add.assert_not_called()
        mock_persist.assert_not_called()

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("jwt.decode")
    def test_decode_exception(self, mock_decode, mock_algo, mock_key):
        mock_decode.side_effect = RuntimeError("network error")
        result = revoke_token("some-token")
        assert result is False

    @patch("app.core.token_manager._get_secret_key", return_value="s")
    @patch("app.core.token_manager._get_algorithm", return_value="HS256")
    @patch("app.core.token_manager._persist_revocation")
    @patch("app.core.token_blacklist.add")
    @patch("jwt.decode")
    def test_no_exp_claim(self, mock_decode, mock_add, mock_persist, mock_algo, mock_key):
        mock_decode.return_value = {"jti": "abc123"}
        result = revoke_token("some-token")
        assert result is True
        mock_add.assert_called_once_with("abc123", expires_at=None)


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


class TestRefreshAccessToken:
    @patch("app.core.token_manager.create_token_pair")
    @patch("app.core.token_manager.revoke_token")
    @patch("app.core.token_manager.validate_token")
    def test_success(self, mock_validate, mock_revoke, mock_create):
        mock_validate.return_value = (True, {"sub": "user1"}, None)
        mock_create.return_value = {"access_token": "new_acc", "refresh_token": "new_ref"}

        success, pair, err = refresh_access_token("refresh-token")

        assert success is True
        assert pair["access_token"] == "new_acc"
        assert err is None
        mock_revoke.assert_called_once_with("refresh-token", reason="refresh_rotation")
        mock_create.assert_called_once_with("user1")

    @patch("app.core.token_manager.validate_token")
    def test_invalid_token(self, mock_validate):
        mock_validate.return_value = (False, None, "令牌已被吊销")
        success, pair, err = refresh_access_token("bad-token")
        assert success is False
        assert err == "令牌已被吊销"

    @patch("app.core.token_manager.validate_token")
    def test_missing_subject(self, mock_validate):
        mock_validate.return_value = (True, {"sub": None}, None)
        success, pair, err = refresh_access_token("refresh-token")
        assert success is False
        assert err == "Refresh token 缺少 subject"


# ---------------------------------------------------------------------------
# TokenManager class (backward compatibility)
# ---------------------------------------------------------------------------


class TestTokenManagerClass:
    def test_create_token_pair(self):
        tm = TokenManager()
        with patch("app.core.token_manager.create_token_pair") as mock:
            mock.return_value = {"access_token": "a", "refresh_token": "b"}
            result = tm.create_token_pair(
                "sub", extra_claims={"r": "a"}, access_ttl_minutes=10, refresh_ttl_days=1
            )
            mock.assert_called_once_with(
                "sub", extra_claims={"r": "a"}, access_ttl_minutes=10, refresh_ttl_days=1
            )
            assert result == {"access_token": "a", "refresh_token": "b"}

    def test_validate_token(self):
        tm = TokenManager()
        with patch("app.core.token_manager.validate_token") as mock:
            mock.return_value = (True, {"sub": "x"}, None)
            result = tm.validate_token("tok", token_type="refresh")
            mock.assert_called_once_with("tok", token_type="refresh")
            assert result == (True, {"sub": "x"}, None)

    def test_revoke_token(self):
        tm = TokenManager()
        with patch("app.core.token_manager.revoke_token") as mock:
            mock.return_value = True
            result = tm.revoke_token("tok", reason="test")
            mock.assert_called_once_with("tok", reason="test")
            assert result is True

    def test_refresh_access_token(self):
        tm = TokenManager()
        with patch("app.core.token_manager.refresh_access_token") as mock:
            mock.return_value = (True, {"access_token": "a"}, None)
            result = tm.refresh_access_token("rtok")
            mock.assert_called_once_with("rtok")
            assert result == (True, {"access_token": "a"}, None)

    def test_create_access_token_no_delta(self):
        tm = TokenManager()
        with patch("app.core.token_manager.create_token_pair") as mock:
            mock.return_value = {"access_token": "acc_tok"}
            result = tm.create_access_token("sub")
            mock.assert_called_once_with("sub", access_ttl_minutes=None)
            assert result == "acc_tok"

    def test_create_access_token_with_delta(self):
        tm = TokenManager()
        with patch("app.core.token_manager.create_token_pair") as mock:
            mock.return_value = {"access_token": "acc_tok"}
            result = tm.create_access_token("sub", expires_delta=timedelta(hours=2))
            mock.assert_called_once_with("sub", access_ttl_minutes=120)
            assert result == "acc_tok"

    def test_decode_token_valid(self):
        tm = TokenManager()
        with patch("app.core.token_manager.validate_token") as mock:
            mock.return_value = (True, {"sub": "u"}, None)
            result = tm.decode_token("tok", expected_type="access")
            assert result == {"sub": "u"}

    def test_decode_token_invalid(self):
        tm = TokenManager()
        with patch("app.core.token_manager.validate_token") as mock:
            mock.return_value = (False, None, "bad")
            result = tm.decode_token("tok", expected_type="access")
            assert result is None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_token_manager_is_instance(self):
        assert isinstance(token_manager, TokenManager)
