"""
RBAC权限管理服务单元测试
覆盖: app/services/rbac_service.py
"""
import pytest
from unittest.mock import MagicMock


class TestPermissionEnum:
    def test_permission_values(self):
        from app.services.rbac_service import Permission
        assert Permission.USER_READ == "user:read"
        assert Permission.USER_WRITE == "user:write"
        assert Permission.USER_DELETE == "user:delete"
        assert Permission.VILLAGE_READ == "village:read"
        assert Permission.VILLAGE_WRITE == "village:write"
        assert Permission.POLICY_READ == "policy:read"
        assert Permission.ORG_READ == "org:read"

    def test_permission_is_string_enum(self):
        from app.services.rbac_service import Permission
        assert issubclass(Permission, str)

    def test_all_permissions_are_colon_format(self):
        from app.services.rbac_service import Permission
        for perm in Permission:
            assert ":" in perm.value

    def test_permission_contains_all_modules(self):
        from app.services.rbac_service import Permission
        values = {p.value for p in Permission}
        modules = set()
        for v in values:
            module = v.split(":")[0]
            modules.add(module)
        assert "user" in modules
        assert "village" in modules
        assert "org" in modules


class TestRBACServiceInit:
    def test_init_creates_service(self):
        from app.services.rbac_service import RBACService
        svc = RBACService()
        assert svc is not None


class TestRBACServiceRoleChecks:
    @pytest.fixture
    def svc(self):
        from app.services.rbac_service import RBACService
        return RBACService()

    def test_has_direct_permission_true(self, svc):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 1
        result = svc._has_direct_permission("1", "village:read", mock_db)
        assert result is True

    def test_has_direct_permission_false(self, svc):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        result = svc._has_direct_permission("1", "village:delete", mock_db)
        assert result is False

    def test_has_role_permission_true(self, svc):
        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.join.return_value \
            .filter.return_value.scalar.return_value = 2
        result = svc._has_role_permission("1", "policy:read", mock_db)
        assert result is True

    def test_has_role_permission_false(self, svc):
        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.join.return_value \
            .filter.return_value.scalar.return_value = 0
        result = svc._has_role_permission("1", "admin:root", mock_db)
        assert result is False


class TestRBACServiceUserRoles:
    @pytest.fixture
    def svc(self):
        from app.services.rbac_service import RBACService
        return RBACService()

    def test_get_user_roles_empty(self, svc):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = svc._get_cached_restricted_permissions(1, mock_db)
        assert result == set()


class TestLogAccess:
    def test_log_access_does_not_raise(self):
        """_log_access should never raise, even with bad inputs."""
        from app.services.rbac_service import RBACService
        mock_db = MagicMock()
        mock_db.add.side_effect = Exception("DB error")
        svc = RBACService()
        # Should not raise
        svc._log_access(
            db=mock_db,
            user_id="user-1",
            action="read",
            resource_type="village",
            resource_id="1",
            access_granted=True,
            reason="test",
        )
        # No exception = success


class TestAdminShortcutByPermission:
    """2026-11-28：管理员捷径按 admin:all 权限判定，不看角色名称。

    角色可由权限包/API 自建，按 name == "admin" 判定会把任意同名自建角色
    当成系统管理员（权限边界漏洞）。
    """

    @staticmethod
    def _db():
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models import Base
        from app.models.rbac import RbacRole, RolePermission, UserRole
        from app.models.user import User

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        user = User(
            username="shortcut_user", full_name="S", hashed_password="x",
            role="user", is_active=True,
        )
        role = RbacRole(
            name="admin", code="LEGACY_ADMIN_NAME", description="d",
            is_system=False, is_active=True, priority=100,
        )
        db.add_all([user, role])
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.add(RolePermission(role_id=role.id, permission="village:read"))
        db.commit()
        return db, engine, user.id, role.id

    def test_role_named_admin_without_admin_all_is_not_admin(self):
        from app.services.rbac_service import RBACService

        db, engine, user_id, _ = self._db()
        try:
            assert RBACService()._has_admin_role(str(user_id), db) is False, \
                "仅凭角色名 admin 不得获得管理员捷径"
        finally:
            db.close()
            engine.dispose()

    def test_role_with_admin_all_permission_is_admin_regardless_of_name(self):
        from app.models.rbac import RbacRole, RolePermission
        from app.services.rbac_service import RBACService

        db, engine, user_id, role_id = self._db()
        try:
            db.query(RbacRole).filter(RbacRole.id == role_id).update(
                {"name": "custom_ops", "code": "CUSTOM_OPS"}
            )
            db.add(RolePermission(role_id=role_id, permission="admin:all"))
            db.commit()
            assert RBACService()._has_admin_role(str(user_id), db) is True, \
                "持有 admin:all 的角色应获得管理员捷径，与名称无关"
        finally:
            db.close()
            engine.dispose()

    def test_named_admin_with_admin_all_perm_still_admin(self):
        from app.models.rbac import RolePermission
        from app.services.rbac_service import RBACService

        db, engine, user_id, role_id = self._db()
        try:
            db.add(RolePermission(role_id=role_id, permission="admin:all"))
            db.commit()
            assert RBACService()._has_admin_role(str(user_id), db) is True
        finally:
            db.close()
            engine.dispose()
