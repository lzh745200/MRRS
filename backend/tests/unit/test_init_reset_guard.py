# -*- coding: utf-8 -*-
"""T047：/system/init/reset 管理员密码二次校验（fail-closed）回归防线。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.system.init import reset_initialization

HASHED = "$2b$12$stubhashstubhashstubhashstubhash"


def _admin():
    return SimpleNamespace(
        id=1,
        username="root",
        role="super_admin",
        is_superuser=True,
        hashed_password=HASHED,
    )


def _run(confirm, admin_password, current_user):
    return asyncio.run(
        reset_initialization(
            confirm=confirm,
            admin_password=admin_password,
            current_user=current_user,
            db=MagicMock(),
        )
    )


class TestInitResetPasswordGuard:
    def test_missing_password_rejected_403(self):
        with pytest.raises(HTTPException) as ei:
            _run("RESET", "", _admin())
        assert ei.value.status_code == 403

    def test_wrong_password_rejected_403(self):
        with patch("app.core.security.verify_password", return_value=False), patch(
            "app.api.v1.system.init.SystemConfigService"
        ) as svc:
            with pytest.raises(HTTPException) as ei:
                _run("RESET", "wrong-password", _admin())
            assert ei.value.status_code == 403
            svc.assert_not_called()

    def test_correct_password_proceeds(self):
        with patch("app.core.security.verify_password", return_value=True), patch(
            "app.api.v1.system.init.SystemConfigService"
        ) as svc_cls:
            svc = MagicMock()
            svc_cls.return_value = svc
            resp = _run("RESET", "Correct#2026", _admin())
            assert resp["success"] is True
            assert svc.set.call_count >= 2

    def test_non_reset_confirm_still_400_before_password(self):
        # confirm 校验先于密码校验（顺序不变）
        with pytest.raises(HTTPException) as ei:
            _run("WRONG", "", _admin())
        assert ei.value.status_code == 400
