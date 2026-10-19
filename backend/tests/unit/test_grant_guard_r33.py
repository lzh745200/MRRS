# -*- coding: utf-8 -*-
"""R33：写接口授权守卫（grant_guard）。

覆盖点：
- `current_mode`：默认 off、合法值透传、非法/空值回落 off（防配置写错锁死全站）；
- `resolve_user`：无头/非 Bearer/空 token/token 无效/缺 sub/用户不存在 全部返回 None；
- `_deny`：shadow 只记日志不抛、enforce 抛 403（含"未映射"与"无权限"两种文案）；
- `enforce_write_grant` 的完整分支：off 短路、读方法放行、豁免放行、用户解析失败放行、
  单位未授权回落 legacy、未映射拒绝、只读拒绝、可写放行。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core import grant_guard as gg


def _req(method="POST", path="/api/v1/projects", auth=None):
    headers = {} if auth is None else {"authorization": auth}
    return SimpleNamespace(method=method, url=SimpleNamespace(path=path), headers=headers)


@pytest.fixture
def fake_db(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
    return db


class TestWiring:
    def test_guard_is_registered_on_app(self):
        """证明守卫真的挂在 app 级依赖上（否则 mode=enforce 也是空转）。"""
        from app.main import app

        deps = {getattr(d, "dependency", None) for d in app.router.dependencies}
        assert gg.enforce_write_grant in deps

    def test_default_mode_is_off(self):
        """出厂默认必须 off，保证升级零行为变化。"""
        from app.core.config import settings

        assert settings.GRANT_GUARD_MODE == "off"


class TestCurrentMode:
    def _with(self, monkeypatch, value):
        monkeypatch.setattr("app.core.config.settings", SimpleNamespace(GRANT_GUARD_MODE=value))
        return gg.current_mode()

    def test_default_off(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings", SimpleNamespace())
        assert gg.current_mode() == gg.MODE_OFF

    def test_shadow(self, monkeypatch):
        assert self._with(monkeypatch, "shadow") == gg.MODE_SHADOW

    def test_enforce_with_whitespace_and_case(self, monkeypatch):
        assert self._with(monkeypatch, "  ENFORCE ") == gg.MODE_ENFORCE

    def test_invalid_falls_back_to_off(self, monkeypatch):
        """配置写错不得把全站写接口锁死。"""
        assert self._with(monkeypatch, "on") == gg.MODE_OFF

    def test_none_falls_back_to_off(self, monkeypatch):
        assert self._with(monkeypatch, None) == gg.MODE_OFF


class TestResolveUser:
    def test_decode_delegates_to_security_module(self, monkeypatch):
        """`_decode` 只是把调用转给 app.core.security.decode_token（保留可替换点）。"""
        monkeypatch.setattr("app.core.security.decode_token", lambda t: {"sub": t})
        assert gg._decode("abc") == {"sub": "abc"}

    def test_no_authorization_header(self, fake_db):
        assert gg.resolve_user(_req(), fake_db) is None

    def test_non_bearer_scheme(self, fake_db):
        assert gg.resolve_user(_req(auth="Basic abc"), fake_db) is None

    def test_empty_token(self, fake_db):
        assert gg.resolve_user(_req(auth="Bearer   "), fake_db) is None

    def test_invalid_token(self, fake_db, monkeypatch):
        monkeypatch.setattr(gg, "_decode", lambda _t: None)
        assert gg.resolve_user(_req(auth="Bearer bad"), fake_db) is None

    def test_missing_sub(self, fake_db, monkeypatch):
        monkeypatch.setattr(gg, "_decode", lambda _t: {"type": "access"})
        assert gg.resolve_user(_req(auth="Bearer t"), fake_db) is None

    def test_user_found(self, fake_db, monkeypatch):
        monkeypatch.setattr(gg, "_decode", lambda _t: {"sub": "alice"})
        fake_db.query.return_value.filter.return_value.first.return_value = "USER"
        assert gg.resolve_user(_req(auth="Bearer t"), fake_db) == "USER"

    def test_user_missing(self, fake_db, monkeypatch):
        monkeypatch.setattr(gg, "_decode", lambda _t: {"sub": "ghost"})
        fake_db.query.return_value.filter.return_value.first.return_value = None
        assert gg.resolve_user(_req(auth="Bearer t"), fake_db) is None


class TestDeny:
    def test_shadow_does_not_raise(self):
        gg._deny(gg.MODE_SHADOW, _req(), "level=view", "projects")

    def test_enforce_raises_with_module(self):
        with pytest.raises(HTTPException) as exc:
            gg._deny(gg.MODE_ENFORCE, _req(), "level=view", "projects")
        assert exc.value.status_code == 403
        assert "录入权限" in exc.value.detail

    def test_enforce_raises_without_module(self):
        with pytest.raises(HTTPException) as exc:
            gg._deny(gg.MODE_ENFORCE, _req(), "unmapped", None)
        assert exc.value.status_code == 403
        assert "映射" in exc.value.detail


class TestEnforceWriteGrant:
    async def test_off_short_circuits(self, monkeypatch, fake_db):
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_OFF)
        await gg.enforce_write_grant(_req())

    async def test_read_method_passes(self, monkeypatch, fake_db):
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        await gg.enforce_write_grant(_req(method="GET"))

    async def test_exempt_path_passes(self, monkeypatch, fake_db):
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        await gg.enforce_write_grant(_req(path="/api/v1/auth/login"))

    async def test_unauthenticated_passes(self, monkeypatch, fake_db):
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: None)
        await gg.enforce_write_grant(_req())

    async def test_legacy_unit_passes(self, monkeypatch, fake_db):
        """单位未下发授权 → 行为与升级前一致，不得拦。"""
        from app.services.effective_grant_service import INACTIVE

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: INACTIVE,
        )
        await gg.enforce_write_grant(_req())

    async def test_unmapped_module_denied_in_enforce(self, monkeypatch, fake_db):
        from app.services.effective_grant_service import GrantMatrix

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "edit"}),
        )
        with pytest.raises(HTTPException) as exc:
            await gg.enforce_write_grant(_req(path="/api/v1/not-a-module/x"))
        assert exc.value.status_code == 403

    async def test_unmapped_module_logged_in_shadow(self, monkeypatch, fake_db):
        """shadow 模式下未映射只告警、不中断（enforce 才抛 403）。"""
        from app.services.effective_grant_service import GrantMatrix

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_SHADOW)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "edit"}),
        )
        await gg.enforce_write_grant(_req(path="/api/v1/not-a-module/x"))
        fake_db.close.assert_called_once()

    async def test_view_only_denied_in_enforce(self, monkeypatch, fake_db):
        from app.services.effective_grant_service import GrantMatrix

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "view"}),
        )
        with pytest.raises(HTTPException) as exc:
            await gg.enforce_write_grant(_req(path="/api/v1/projects/1"))
        assert exc.value.status_code == 403

    async def test_view_only_logged_in_shadow(self, monkeypatch, fake_db):
        from app.services.effective_grant_service import GrantMatrix

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_SHADOW)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "view"}),
        )
        await gg.enforce_write_grant(_req(path="/api/v1/projects/1"))

    async def test_edit_allowed(self, monkeypatch, fake_db):
        from app.services.effective_grant_service import GrantMatrix

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "edit"}),
        )
        await gg.enforce_write_grant(_req(path="/api/v1/projects/1"))
        fake_db.close.assert_called_once()

    async def test_session_closed_even_on_deny(self, monkeypatch, fake_db):
        from app.services.effective_grant_service import GrantMatrix

        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: "USER")
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "none"}),
        )
        with pytest.raises(HTTPException):
            await gg.enforce_write_grant(_req(path="/api/v1/projects/1"))
        fake_db.close.assert_called_once()
