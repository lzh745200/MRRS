# -*- coding: utf-8 -*-
"""system/init.py 覆盖率测试：initialize 分支 + reset 分支"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.system.init as mod


def _svc(initialized=False):
    svc = MagicMock()
    svc.is_initialized.return_value = initialized
    return svc


def _req(**kw):
    base = dict(
        organization_name="某单位",
        admin_username="admin",
        admin_password="Abcd1234!@#$",
    )
    base.update(kw)
    return mod.InitRequest(**base)


# ---------- initialize ----------

@pytest.mark.asyncio
async def test_initialize_weak_password_400():
    pp = MagicMock()
    pp.validate.return_value = (False, "密码强度不足")
    with patch.object(mod, "SystemConfigService", return_value=_svc(False)), patch.object(
        mod, "PasswordPolicy", pp
    ):
        with pytest.raises(HTTPException) as exc:
            await mod.initialize_system(request=_req(), db=MagicMock())
    assert exc.value.status_code == 400
    assert exc.value.detail == "密码强度不足"


@pytest.mark.asyncio
async def test_initialize_full_optional_fields_and_existing_admin():
    svc = _svc(False)
    pp = MagicMock()
    pp.validate.return_value = (True, None)
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = MagicMock()  # 管理员已存在 → skipped
    db.query.return_value = q
    req = _req(
        organization_short_name="某部",
        organization_code="ORG001",
        contact_person="张三",
        contact_phone="13800000000",
    )
    with patch.object(mod, "SystemConfigService", return_value=svc), patch.object(
        mod, "PasswordPolicy", pp
    ):
        resp = await mod.initialize_system(request=req, db=db)
    assert resp["success"] is True
    steps = {s["step"]: s["status"] for s in resp["data"]["steps"]}
    assert steps["admin_user"] == "skipped"
    assert steps["config"] == "success"
    # 可选字段全部写入
    set_keys = [c.args[0] for c in svc.set.call_args_list]
    for k in ("organization_short_name", "organization_code", "contact_person", "contact_phone"):
        assert k in set_keys
    svc.set_initialized.assert_called_once_with(org_id=1)


@pytest.mark.asyncio
async def test_initialize_admin_creation_failure_warns():
    svc = _svc(False)
    pp = MagicMock()
    pp.validate.return_value = (True, None)
    db = MagicMock()
    db.query.side_effect = RuntimeError("db down")
    with patch.object(mod, "SystemConfigService", return_value=svc), patch.object(
        mod, "PasswordPolicy", pp
    ):
        resp = await mod.initialize_system(request=_req(), db=db)
    assert resp["success"] is True
    steps = {s["step"]: s["status"] for s in resp["data"]["steps"]}
    assert steps["admin_user"] == "warning"
    assert "db down" in resp["data"]["steps"][2]["message"]


@pytest.mark.asyncio
async def test_initialize_outer_exception_500():
    svc = MagicMock()
    svc.is_initialized.side_effect = RuntimeError("config table missing")
    with patch.object(mod, "SystemConfigService", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await mod.initialize_system(request=_req(), db=MagicMock())
    assert exc.value.status_code == 500
    assert "系统初始化失败" in exc.value.detail


# ---------- reset ----------

@pytest.mark.asyncio
async def test_reset_not_admin_403():
    with patch("app.core.permission_utils.is_admin", return_value=False):
        with pytest.raises(HTTPException) as exc:
            await mod.reset_initialization(confirm="RESET", current_user=MagicMock(), db=MagicMock())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reset_service_exception_500():
    svc = MagicMock()
    svc.set.side_effect = RuntimeError("write fail")
    with patch("app.core.permission_utils.is_admin", return_value=True), patch.object(
        mod, "SystemConfigService", return_value=svc
    ):
        with pytest.raises(HTTPException) as exc:
            await mod.reset_initialization(confirm="RESET", current_user=MagicMock(), db=MagicMock())
    assert exc.value.status_code == 500
    assert "重置失败" in exc.value.detail
