"""授权策略门面（off/shadow/enforce）单元测试。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import authorize as authz
from app.core.config import settings
from app.core.permission_utils import require_admin


def _user(role="user", is_superuser=False):
    return SimpleNamespace(id=7, role=role, is_superuser=is_superuser)


class TestAuthorizeFacade:
    def test_off_returns_legacy(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTHORIZE_MODE", "off")
        assert authz.authorize(_user(), "admin", legacy_allowed=True) is True
        assert authz.authorize(_user(), "admin", legacy_allowed=False) is False

    def test_shadow_keeps_legacy_even_when_policy_differs(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "AUTHORIZE_MODE", "shadow")
        # 非管理员 + legacy=True 是差异场景：shadow 必须继续放行 legacy，只记日志。
        assert authz.authorize(_user(), "admin", legacy_allowed=True) is True
        assert "授权 shadow 差异" in caplog.text

    def test_enforce_uses_policy(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTHORIZE_MODE", "enforce")
        assert authz.authorize(_user(), "admin", legacy_allowed=True) is False
        assert authz.authorize(_user(role="admin"), "admin", legacy_allowed=False) is True
        assert authz.authorize(_user(role="super_admin"), "superuser", legacy_allowed=False) is True

    def test_unknown_action_does_not_amplify(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTHORIZE_MODE", "enforce")
        assert authz.authorize(_user(), "unregistered", legacy_allowed=False) is True

    @pytest.mark.parametrize("raw", ["", "0", "false", "off", "bogus"])
    def test_mode_aliases_fall_back_to_off(self, monkeypatch, raw):
        monkeypatch.setattr(settings, "AUTHORIZE_MODE", raw)
        assert authz.current_mode() == "off"

    def test_require_admin_still_denies_non_admin(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTHORIZE_MODE", "shadow")
        with pytest.raises(HTTPException) as exc:
            require_admin(_user())
        assert exc.value.status_code == 403
