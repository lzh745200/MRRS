"""
API 依赖测试

测试 app/api/v1/deps.py 模块
"""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.api.v1.deps import require_manager_role


class TestRequireManagerRole:
    def test_admin_role_passes(self):
        user = MagicMock(role="admin", is_superuser=False)
        require_manager_role(user)

    def test_super_admin_role_passes(self):
        user = MagicMock(role="super_admin", is_superuser=False)
        require_manager_role(user)

    def test_manager_role_passes(self):
        user = MagicMock(role="manager", is_superuser=False)
        require_manager_role(user)

    def test_user_role_raises(self):
        user = MagicMock(role="user", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            require_manager_role(user)
        assert exc.value.status_code == 403

    def test_empty_role_raises(self):
        user = MagicMock(role="", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            require_manager_role(user)
        assert exc.value.status_code == 403

    def test_superuser_passes_without_role(self):
        user = MagicMock(role="user", is_superuser=True)
        require_manager_role(user)

    def test_none_role_raises(self):
        user = MagicMock(role=None, is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            require_manager_role(user)
        assert exc.value.status_code == 403
