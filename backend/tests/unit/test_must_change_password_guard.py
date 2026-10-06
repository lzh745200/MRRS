"""服务端「首登强制改密」拦截（2026-10-06）。

历史缺陷：``must_change_password`` 只在登录响应里回传，"未改密不得使用系统"
**仅由前端 ``router/guards.ts`` 收口** —— 用 curl/脚本直接登录即可携带最高权限
调用全部业务端点，出厂口令的"首登强制改密"承诺形同虚设（且该口令是公开常识值）。

现在由 ``core/security.py::get_current_user`` 做服务端兜底：
未完成改密前只放行「取得身份 + 完成改密 + 登出/续期 + 菜单骨架」。
"""

import pytest

from app.core.security import (
    _must_change_password_request_allowed,
    create_access_token,
    get_password_hash,
)


class TestAllowList:
    """放行集与前端 ``changePasswordWhitelist`` 对应，并补齐改密链路自身所需接口。"""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/auth/refresh",
            "/api/v1/auth/csrf-token",
            "/api/v1/users/me",
            "/api/v1/menus/accessible",
        ],
    )
    def test_auth_bootstrap_paths_allowed(self, path):
        assert _must_change_password_request_allowed("GET", path, 1) is True

    def test_preflight_allowed(self):
        """OPTIONS 必须放行，否则跨域预检失败会让改密页自己发不出请求。"""
        assert _must_change_password_request_allowed("OPTIONS", "/api/v1/policies", 1) is True

    def test_own_password_change_allowed(self):
        assert _must_change_password_request_allowed("PUT", "/api/v1/users/7/password", 7) is True

    def test_other_user_password_change_denied(self):
        """只放行「改自己」；管理员改他人密码同样要先完成首登改密。"""
        assert _must_change_password_request_allowed("PUT", "/api/v1/users/8/password", 7) is False

    def test_password_path_without_user_id_denied(self):
        assert _must_change_password_request_allowed("PUT", "/api/v1/users/8/password", None) is False

    @pytest.mark.parametrize(
        "path",
        ["/api/v1/policies", "/api/v1/funds", "/api/v1/system/backup", "/api/v1/rbac/roles"],
    )
    def test_business_paths_denied(self, path):
        assert _must_change_password_request_allowed("GET", path, 1) is False

    def test_unknown_path_fail_closed(self):
        """fail-closed：无法判定路径（非 HTTP 直调）时一并拦截。"""
        assert _must_change_password_request_allowed("", "", 1) is False
        assert _must_change_password_request_allowed("GET", "", None) is False


class TestEnforcedOverHttp:
    """真实 HTTP 链路验证（同时证明 FastAPI 确实注入了 Request 对象）。"""

    USERNAME = "mc_guard_admin"

    def _seed_user(self, must_change: bool = True):
        from app.core.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        existing = db.query(User).filter(User.username == self.USERNAME).first()
        if existing is not None:
            existing.must_change_password = must_change
            db.commit()
            return existing.id
        user = User(
            username=self.USERNAME,
            hashed_password=get_password_hash("InitPass#12345"),
            role="admin",
            is_active=True,
            is_superuser=True,
            must_change_password=must_change,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
        db.close()
        return uid

    def _clear_flag(self, uid: int):
        from app.core.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        db.query(User).filter(User.id == uid).update({User.must_change_password: False})
        db.commit()
        db.close()

    def _headers(self):
        return {"Authorization": f"Bearer {create_access_token({'sub': self.USERNAME})}"}

    def test_business_endpoint_blocked_until_password_changed(self, client):
        uid = self._seed_user(must_change=True)
        headers = self._headers()

        resp = client.get("/api/v1/policies", headers=headers)
        assert resp.status_code == 403
        assert "初始密码" in resp.json()["detail"]

        # 改密链路自身必须放行，否则用户永远无法完成改密（死锁）
        assert client.get("/api/v1/users/me", headers=headers).status_code != 403

        # 完成改密后恢复访问
        self._clear_flag(uid)
        assert client.get("/api/v1/policies", headers=headers).status_code == 200

    def test_flag_false_user_unaffected(self, client):
        """普通用户（未标记强制改密）不受影响 —— 防止误伤存量账号。"""
        self._seed_user(must_change=False)
        assert client.get("/api/v1/policies", headers=self._headers()).status_code == 200
