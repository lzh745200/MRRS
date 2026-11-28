"""自助注册能力下线回归。

产品不再提供自助注册：账号由管理员或权限包创建。本文件锁定三条契约：
1. ``POST /api/v1/auth/register`` 路由不存在（404/405，而不是业务 403）；
2. 登录页公开配置不再返回 ``self_register_enabled``；
3. 公开配置仍保留锁定策略字段（登录页倒计时依赖）。

机器码绑定 / 通行码激活 / 密码重置 / 管理员开户能力不受影响，
服务层覆盖见 ``test_org_passcode_cross_machine.py``。
"""


class TestRegisterEndpointRemoved:
    prefix = "/api/v1/auth"

    def test_register_route_is_not_registered(self):
        """路由表里不得再出现注册端点。"""
        from app.main import app

        paths = {getattr(route, "path", None) for route in app.routes}
        assert f"{self.prefix}/register" not in paths

    def test_post_register_returns_404(self, client):
        """调用已删除端点应为 404/405（路由缺失），而不是 403。"""
        response = client.post(
            f"{self.prefix}/register",
            json={
                "username": "newuser",
                "password": "Str0ng!Passw0rd",
                "pass_code": "code123",
            },
        )
        assert response.status_code in (404, 405)

    def test_public_config_has_no_self_register_flag(self, client):
        response = client.get(f"{self.prefix}/public-config")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "self_register_enabled" not in data
        # 登录页锁定倒计时仍依赖这两个非敏感策略参数
        assert "lockout_minutes" in data
        assert "max_failed_attempts" in data
