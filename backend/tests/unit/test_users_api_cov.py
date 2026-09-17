"""app.api.v1.auth.users 覆盖率攻坚测试（补充既有测试未覆盖分支）

覆盖点：
- get_staff_list：DataScope.OWN / OWN_DEPT 过滤分支
- change_password：admin 临时密码文件清理（成功+异常降级）、审计日志失败降级
- upload_avatar：403/404/类型400/超大小400/成功/扩展名回退
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.auth.users as us
from app.core.data_permission import DataScope
from app.core.exceptions import NotFoundException


def _user(**kw):
    defaults = dict(
        id=1, username="admin", role="admin", is_superuser=True, organization_id=1,
        full_name="管理员", department=None, position=None, avatar=None,
        hashed_password="hashed-old", must_change_password=True,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit"):
        getattr(q, attr).return_value = q
    q.count.return_value = kw.get("count", 0)
    q.all.return_value = kw.get("all", [])
    q.first.return_value = kw.get("first")
    return q


def _db(*queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


class TestStaffListScopes:
    # 注意：users.py 在模块级导入 get_data_scope，补丁目标必须是使用者模块
    _PATCH = "app.api.v1.auth.users.get_data_scope"

    async def test_own_scope(self):
        u = _user(id=5, is_superuser=False)
        db = _db(_q(count=1, all=[u]))
        with patch(self._PATCH, return_value=DataScope.OWN):
            result = await us.get_staff_list(page=1, page_size=20, current_user=u, db=db)
        assert result["data"]["total"] == 1

    async def test_own_dept_scope(self):
        u = _user(id=5, is_superuser=False, organization_id=7)
        db = _db(_q(count=1, all=[u]))
        with patch(self._PATCH, return_value=DataScope.OWN_DEPT):
            result = await us.get_staff_list(page=1, page_size=20, current_user=u, db=db)
        assert result["data"]["total"] == 1


class TestChangePasswordCleanup:
    def _setup_user(self):
        user = _user(username="admin")
        user.revoke_all_tokens = lambda: None
        return user

    async def _call(self, user, current):
        db = _db(_q(first=user))
        data = SimpleNamespace(old_password="old", new_password="NewPass!234")
        with (
            patch("app.core.security.verify_password", return_value=True),
            patch("app.core.security.PasswordPolicy") as m_policy,
            patch.object(us, "get_password_hash", return_value="hashed"),
            patch.object(us, "safe_commit"),
        ):
            m_policy.validate.return_value = (True, "")
            return await us.change_password(1, data, current, db)

    async def test_admin_temp_file_cleanup_success(self):
        with (
            patch("glob.glob", return_value=["/tmp/admin_pwd_1.txt"]),
            patch("os.remove") as m_remove,
            patch("app.services.work_log_service.write_work_log"),
        ):
            result = await self._call(self._setup_user(), _user())
        assert result["code"] == 200
        m_remove.assert_called_once()

    async def test_cleanup_exception_degrades(self):
        with (
            patch("glob.glob", side_effect=RuntimeError("glob boom")),
            patch("app.services.work_log_service.write_work_log"),
        ):
            result = await self._call(self._setup_user(), _user())
        assert result["code"] == 200

    async def test_audit_log_failure_degrades(self):
        with (
            patch("glob.glob", return_value=[]),
            patch("app.services.work_log_service.write_work_log", side_effect=RuntimeError("audit boom")),
        ):
            result = await self._call(self._setup_user(), _user())
        assert result["code"] == 200


class TestUploadAvatar:
    def _avatar(self, content_type="image/png", content=b"x", filename="a.png"):
        return SimpleNamespace(
            content_type=content_type, filename=filename,
            read=AsyncMock(return_value=content),
        )

    async def test_forbidden_403(self):
        current = _user(id=2, is_superuser=False)
        with pytest.raises(HTTPException) as exc_info:
            await us.upload_avatar(1, self._avatar(), current, MagicMock())
        assert exc_info.value.status_code == 403

    async def test_user_not_found(self):
        db = _db(_q(first=None))
        with pytest.raises(NotFoundException):
            await us.upload_avatar(1, self._avatar(), _user(), db)

    async def test_invalid_content_type_400(self):
        db = _db(_q(first=_user()))
        with pytest.raises(HTTPException) as exc_info:
            await us.upload_avatar(1, self._avatar(content_type="text/plain"), _user(), db)
        assert exc_info.value.status_code == 400

    async def test_oversize_400(self):
        db = _db(_q(first=_user()))
        big = self._avatar(content=b"x" * (2 * 1024 * 1024 + 1))
        with pytest.raises(HTTPException) as exc_info:
            await us.upload_avatar(1, big, _user(), db)
        assert exc_info.value.status_code == 400

    async def test_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr(us.settings, "UPLOAD_DIR", str(tmp_path))
        user = _user()
        db = _db(_q(first=user))
        with patch.object(us, "safe_commit"):
            result = await us.upload_avatar(1, self._avatar(), _user(), db)
        assert result["code"] == 200
        assert result["avatar_url"].endswith(".png")
        assert user.avatar == result["avatar_url"]

    async def test_bad_extension_falls_back_png(self, tmp_path, monkeypatch):
        monkeypatch.setattr(us.settings, "UPLOAD_DIR", str(tmp_path))
        user = _user()
        db = _db(_q(first=user))
        with patch.object(us, "safe_commit"):
            result = await us.upload_avatar(1, self._avatar(filename="a.bmp"), _user(), db)
        assert result["avatar_url"].endswith(".png")
