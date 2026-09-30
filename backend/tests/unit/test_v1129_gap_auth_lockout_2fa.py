"""v1.12.9 覆盖率补口：app/api/v1/auth/auth.py（W15 深审 #3/#4）。

覆盖行（当前代码行号）：
- 114-139 `_discard_orphan_user`：注册失败清理半成品用户 ——
  成功路径（回滚→删除→提交）/ 首次回滚异常被吞 / 删除失败降级（含二次回滚也失败）
  必须全程不抛：注册流程"全成功或全不落库"，清理失败不能反向把注册打成 500；
- 409-423 `/auth/two-factor/verify-login`：2FA 校验失败达锁定阈值时
  吊销 temp_token 并返回 423（修复前失败只写审计日志、既不计数也不吊销，
  攻击者凭一个 temp_token 即可无限次枚举动态码）；
- 562-575 `_bump_token_version`：登出时命中用户 → 递增 token_version 并提交（ADR-0001）。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import app.api.v1.auth.auth as auth_mod


class TestDiscardOrphanUser:
    """清理注册残留的半成品用户（W15 深审 #3）。"""

    def test_none_user_is_noop(self):
        db = Mock()
        auth_mod._discard_orphan_user(db, None)
        db.delete.assert_not_called()
        db.rollback.assert_not_called()

    def test_success_rolls_back_deletes_and_commits(self):
        db = Mock()
        user = SimpleNamespace(id=101, username="orphan")
        with patch.object(auth_mod, "safe_commit") as m_commit:
            auth_mod._discard_orphan_user(db, user)
        db.rollback.assert_called_once()
        db.delete.assert_called_once_with(user)
        m_commit.assert_called_once_with(db)

    def test_first_rollback_failure_is_swallowed(self):
        """首次回滚本身失败（会话已失效）不能阻断删除。"""
        db = Mock()
        db.rollback.side_effect = RuntimeError("session already invalidated")
        user = SimpleNamespace(id=102, username="orphan2")
        with patch.object(auth_mod, "safe_commit") as m_commit:
            auth_mod._discard_orphan_user(db, user)
        db.delete.assert_called_once_with(user)
        m_commit.assert_called_once_with(db)

    def test_delete_failure_rolls_back_and_is_contained(self):
        """删除失败 → 兜底回滚 + 记错误日志，绝不向上抛。"""
        db = Mock()
        user = SimpleNamespace(id=103, username="orphan3")
        db.delete.side_effect = RuntimeError("stale object state")
        auth_mod._discard_orphan_user(db, user)
        assert db.rollback.call_count == 2  # 首次回滚 + 删除失败后的兜底回滚

    def test_delete_and_second_rollback_failure_is_contained(self):
        """删除与二次回滚同时失败：异常必须被吞掉（注册流程不能因此 500）。"""
        db = Mock()
        user = SimpleNamespace(id=104, username="orphan4")
        db.delete.side_effect = RuntimeError("stale object state")
        db.rollback.side_effect = [None, RuntimeError("rollback also failed")]
        auth_mod._discard_orphan_user(db, user)
        assert db.rollback.call_count == 2


class TestTwoFactorVerifyLoginLockout:
    """2FA 失败与 /auth/login 同口径：达阈值 → 吊销 temp_token + 423（W15 深审 #4）。"""

    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_threshold_reached_revokes_temp_token(
        self, mock_tm, mock_usr_svc, mock_ip, mock_rl, client
    ):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser", "two_factor_pending": True}
        user = SimpleNamespace(
            id=7, username="testuser", is_active=True, role="user",
            failed_login_count=auth_mod._MAX_FAILED_ATTEMPTS - 1, locked_until=None,
            hashed_password="h",
        )
        svc = Mock()
        svc.get_user_by_username.return_value = user
        mock_usr_svc.return_value = svc

        with patch("app.services.two_factor_service.TwoFactorService") as mock_2fa, patch.object(
            auth_mod, "_handle_failed_login", return_value=auth_mod._MAX_FAILED_ATTEMPTS
        ) as m_failed:
            mock_2fa.verify_login.return_value = False
            resp = client.post(
                f"{self.prefix}/two-factor/verify-login",
                json={"temp_token": "temp-token-x", "code": "000000"},
            )

        assert resp.status_code == 423
        assert "账户已锁定" in resp.json()["detail"]
        mock_tm.revoke_token.assert_called_once_with("temp-token-x")
        assert m_failed.call_args.kwargs["failure_reason"] == "2FA验证码错误"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_below_threshold_keeps_temp_token(
        self, mock_tm, mock_usr_svc, mock_ip, mock_rl, client
    ):
        """未达阈值：401 且不吊销临时令牌（计数/锁定交给 lockout_service）。"""
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser", "two_factor_pending": True}
        user = SimpleNamespace(
            id=8, username="testuser", is_active=True, role="user",
            failed_login_count=1, locked_until=None, hashed_password="h",
        )
        svc = Mock()
        svc.get_user_by_username.return_value = user
        mock_usr_svc.return_value = svc

        with patch("app.services.two_factor_service.TwoFactorService") as mock_2fa, patch.object(
            auth_mod, "_handle_failed_login", return_value=auth_mod._MAX_FAILED_ATTEMPTS - 1
        ):
            mock_2fa.verify_login.return_value = False
            resp = client.post(
                f"{self.prefix}/two-factor/verify-login",
                json={"temp_token": "temp-token-y", "code": "000000"},
            )

        assert resp.status_code == 401
        assert "验证码错误" in resp.json()["detail"]
        mock_tm.revoke_token.assert_not_called()


class TestBumpTokenVersion:
    """登出时失效全部历史 JWT（W1-T5 / ADR-0001）。"""

    @patch("app.api.v1.auth.auth.UserService")
    def test_existing_user_increments_and_commits(self, mock_usr_svc):
        db = Mock()
        svc_user = SimpleNamespace(token_version=3)
        mock_usr_svc.return_value.get_user_by_username.return_value = svc_user
        with patch.object(auth_mod, "safe_commit") as m_commit:
            auth_mod._bump_token_version(db, "testuser")
        assert svc_user.token_version == 4
        m_commit.assert_called_once_with(db)

    @patch("app.api.v1.auth.auth.UserService")
    def test_unknown_user_is_noop(self, mock_usr_svc):
        db = Mock()
        mock_usr_svc.return_value.get_user_by_username.return_value = None
        with patch.object(auth_mod, "safe_commit") as m_commit:
            auth_mod._bump_token_version(db, "ghost")
        m_commit.assert_not_called()
