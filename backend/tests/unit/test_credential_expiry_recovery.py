"""P0 回归：初始凭据有效期到期后必须能被"改密/管理员重置"解除。

审计发现（2026-11-21）：账号开通包签发的账号带 ``credential_expires_at``（默认 30 天），
登录口 ``enforce_credential_not_expired`` 到期即 403；而改密与管理员重置都只清
``must_change_password``，不清该字段 —— 到期后任何常规操作都救不回来，只能改库。
另外过期任务会把这类账号 ``is_active=False``，重置密码若不恢复启用，仍然登不进去。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app.core.database import get_db
from app.core.security import get_current_user

from tests.unit.test_auth_users_api import (
    _clear_overrides,
    _make_mock_db,
    _make_user,
    _override_db,
    _setup_admin_user,
    _setup_regular_user,
)

PREFIX = "/api/v1/users"


class TestCredentialExpiryRecovery:
    def test_change_password_clears_credential_expiry(self, client):
        """自助改密成功后必须清空初始凭据有效期，否则到期即永久锁死。"""
        _setup_regular_user(client)
        user = _make_user(id=2, username="regular")
        # 注意：_make_user 只认识固定字段，过期时间必须显式赋值（否则是 Mock 属性）
        user.credential_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        _override_db(client, _make_mock_db(user=user))
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.verify_password", return_value=True):
                with patch("app.core.security.PasswordPolicy") as mock_policy:
                    mock_policy.validate.return_value = (True, "")
                    with patch("app.api.v1.auth.users.get_password_hash", return_value="new_hash"):
                        resp = client.put(
                            f"{PREFIX}/2/password",
                            json={"old_password": "correct", "new_password": "NewStr0ng!Pass"},
                        )
        assert resp.status_code == 200
        assert user.credential_expires_at is None
        _clear_overrides(client, get_db, get_current_user)

    def test_admin_reset_clears_expiry_and_reactivates(self, client):
        """管理员重置：清有效期 + 因过期被停用的账号恢复启用（两道门都要开）。"""
        _setup_admin_user(client)
        user = _make_user(id=2, is_active=False, role="user")
        user.credential_expires_at = datetime.now(timezone.utc) - timedelta(days=3)
        _override_db(client, _make_mock_db(user=user))
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.PasswordPolicy") as mock_policy:
                mock_policy.validate.return_value = (True, "")
                with patch("app.api.v1.auth.users.get_password_hash", return_value="new_hash"):
                    resp = client.post(
                        f"{PREFIX}/2/admin-reset-password",
                        json={"new_password": "NewStr0ng!Pass"},
                    )
        assert resp.status_code == 200
        assert user.credential_expires_at is None
        assert user.is_active is True
        _clear_overrides(client, get_db, get_current_user)

    def test_admin_reset_keeps_manually_disabled_user_inactive(self, client):
        """没有过期标记的停用账号（人工停用/待审核）不得被重置密码顺手启用。"""
        _setup_admin_user(client)
        user = _make_user(id=2, is_active=False, role="user")
        user.credential_expires_at = None
        _override_db(client, _make_mock_db(user=user))
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.PasswordPolicy") as mock_policy:
                mock_policy.validate.return_value = (True, "")
                with patch("app.api.v1.auth.users.get_password_hash", return_value="new_hash"):
                    resp = client.post(
                        f"{PREFIX}/2/admin-reset-password",
                        json={"new_password": "NewStr0ng!Pass"},
                    )
        assert resp.status_code == 200
        assert user.credential_expires_at is None
        assert user.is_active is False
        _clear_overrides(client, get_db, get_current_user)
