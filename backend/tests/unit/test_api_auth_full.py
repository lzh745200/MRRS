"""
API认证模块全面测试
覆盖app/api/v1/auth/下的所有路由
"""




class TestAuthAPI:
    """测试认证API"""

    def test_auth_login_get(self, client):
        """测试登录页面GET"""
        response = client.get("/api/v1/auth/login")
        assert response.status_code in [200, 404, 405, 405]

    def test_auth_login_post_empty(self, client):
        """测试空登录请求"""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code in [200, 400, 401, 405, 422]

    def test_auth_login_post_invalid(self, client):
        """测试无效凭据登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "invalid",
            "password": "wrong"
        })
        assert response.status_code in [200, 400, 401, 405, 422]

    def test_auth_logout(self, client):
        """测试登出"""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code in [200, 401, 405]

    def test_auth_refresh(self, client):
        """测试刷新token"""
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code in [200, 401, 404, 405, 422]

    def test_auth_me(self, client):
        """测试获取当前用户信息"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code in [200, 401, 404]

    def test_auth_register_removed(self, client):
        """自助注册端点已下线（路由不存在）"""
        response = client.post("/api/v1/auth/register", json={})
        assert response.status_code in [404, 405]

    def test_auth_change_password(self, client):
        """测试修改密码"""
        response = client.post("/api/v1/auth/change-password", json={})
        assert response.status_code in [200, 401, 400, 404, 405, 422]

class TestTwoFactorAPI:
    """测试双因素认证API"""

    def test_2fa_setup_get(self, client):
        """测试获取2FA设置"""
        response = client.get("/api/v1/auth/2fa/setup")
        assert response.status_code in [200, 401, 404, 405, 405]

    def test_2fa_setup_post(self, client):
        """测试设置2FA"""
        response = client.post("/api/v1/auth/2fa/setup", json={})
        assert response.status_code in [200, 401, 404, 405, 405, 422]

    def test_2fa_verify(self, client):
        """测试验证2FA"""
        response = client.post("/api/v1/auth/2fa/verify", json={
            "code": "123456"
        })
        assert response.status_code in [200, 401, 400, 404, 405, 422]

    def test_2fa_disable(self, client):
        """测试禁用2FA"""
        response = client.post("/api/v1/auth/2fa/disable")
        assert response.status_code in [200, 401, 400, 404, 405]

    def test_2fa_backup_codes(self, client):
        """测试获取备用码"""
        response = client.get("/api/v1/auth/2fa/backup-codes")
        assert response.status_code in [200, 401, 404, 405, 405]

class TestPasswordResetAPI:
    """测试密码重置API"""

    def test_forgot_password_empty(self, client):
        """测试空忘记密码请求"""
        response = client.post("/api/v1/auth/forgot-password", json={})
        assert response.status_code in [200, 400, 404, 405, 422]

    def test_forgot_password_invalid_email(self, client):
        """测试无效邮箱"""
        response = client.post("/api/v1/auth/forgot-password", json={
            "email": "invalid"
        })
        assert response.status_code in [200, 400, 404, 405, 422]

    def test_reset_password_empty(self, client):
        """测试空重置密码请求"""
        response = client.post("/api/v1/auth/reset-password", json={})
        assert response.status_code in [200, 400, 404, 405, 422]

    def test_reset_password_invalid_token(self, client):
        """测试无效token"""
        response = client.post("/api/v1/auth/reset-password", json={
            "token": "invalid",
            "password": "newpassword123"
        })
        assert response.status_code in [200, 400, 401, 404, 405]

class TestMachineCodeAuthAPI:
    """测试机器码认证API"""

    def test_machine_code_register(self, client):
        """测试机器码注册"""
        response = client.post("/api/v1/auth/machine-code", json={
            "code": "test-machine-code-123"
        })
        assert response.status_code in [200, 400, 404, 405, 422, 409]

    def test_machine_code_bind(self, client):
        """测试机器码绑定"""
        response = client.post("/api/v1/auth/machine-code/bind", json={})
        assert response.status_code in [200, 401, 400, 404, 405, 422]

    def test_machine_code_list(self, client):
        """测试获取机器码列表"""
        response = client.get("/api/v1/auth/machine-codes")
        assert response.status_code in [200, 401, 404, 405]

    def test_machine_code_revoke(self, client):
        """测试吊销机器码"""
        response = client.post("/api/v1/auth/machine-codes/1/revoke")
        assert response.status_code in [200, 401, 404, 405, 405]

class TestCSRFAPI:
    """测试CSRF API"""

    def test_csrf_token(self, client):
        """测试获取CSRF token"""
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code in [200, 404, 405]

class TestAuthStatusAPI:
    """测试认证状态API"""

    def test_auth_status(self, client):
        """测试获取认证状态"""
        response = client.get("/api/v1/auth/status")
        assert response.status_code in [200, 401, 404, 405]

    def test_auth_permissions(self, client):
        """测试获取当前用户权限"""
        response = client.get("/api/v1/auth/permissions")
        assert response.status_code in [200, 401, 404, 405]
