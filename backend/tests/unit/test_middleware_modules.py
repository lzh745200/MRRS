"""
Middleware模块全面测试
覆盖app/middleware/下的所有模块
"""


from unittest.mock import MagicMock

# 注：app.middleware.auth 与 app.middleware.rbac 模块已移除
# （认证改由 app.core.security 依赖注入；RBAC 改由 app.core.rbac 依赖注入），
# 原 TestAuthMiddleware / TestRBACMiddleware 死代码已删除。




# 注：app.middleware.prometheus_middleware 模块已移除
# （指标改由 app.middleware.metrics_middleware 提供），
# 原 TestPrometheusMiddleware 死代码已删除。

class TestAuditContext:
    """测试审计上下文"""

    def test_audit_context_import(self):
        """测试审计上下文导入"""
        from app.middleware.audit_context import AuditContext
        assert AuditContext is not None

    def test_get_current_user(self):
        """测试获取当前用户"""
        from app.middleware.audit_context import get_current_user
        assert callable(get_current_user)

    def test_get_request_id(self):
        """测试获取请求ID"""
        from app.middleware.audit_context import get_request_id
        assert callable(get_request_id)

