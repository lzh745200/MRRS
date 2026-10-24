# -*- coding: utf-8 -*-
"""P3 自检端点：管理员可见、非管理员 403。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user


def _admin():
    return SimpleNamespace(id=1, username="admin", role="super_admin", is_superuser=True, is_active=True)


def _normal_user():
    return SimpleNamespace(id=2, username="bob", role="user", is_superuser=False, is_active=True)


@pytest.fixture
def make_client():
    from app.main import app

    created = []

    def _make(user):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0

        def _get_db():
            yield db

        async def _current_user():
            return user

        original = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_current_user] = _current_user
        client = TestClient(app, raise_server_exceptions=False)
        created.append((app, original))
        return client

    yield _make
    for app_, original in created:
        app_.dependency_overrides = original


class TestSelfCheckEndpoint:
    def test_admin_gets_report(self, make_client):
        client = make_client(_admin())
        with patch("app.core.pii_crypto.key_fingerprint", return_value="abcdef1234567890"):
            resp = client.get("/api/v1/system/self-check")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        data = body.get("data", body)
        assert data["status"] in ("ok", "warn", "error")
        assert data["summary"]["check_count"] == 6
        assert len(data["checks"]) == 6

    def test_non_admin_forbidden(self, make_client):
        client = make_client(_normal_user())
        resp = client.get("/api/v1/system/self-check")
        assert resp.status_code == 403


class TestSelfCheckRouteContract:
    """路径契约：必须挂在 system 包聚合路由下（/api/v1/system/*）。

    历史缺陷：模块曾单独挂在 `/api/v1` 根级，而前端调用 `/system/self-check`
    → 真机上自检卡片恒 404。此用例锁死路径与前端调用一致。
    """

    PREFIX = "/api/v1/system"

    def test_route_registered_under_system(self):
        from app.main import app

        paths = {getattr(r, "path", "") for r in app.routes}
        assert "/api/v1/system/self-check" in paths
        assert "/api/v1/self-check" not in paths

    def test_frontend_calls_same_path(self):
        import pathlib

        fe = pathlib.Path(__file__).resolve().parents[3] / "frontend/src/api/selfCheck.ts"
        if not fe.exists():  # pragma: no cover - 前端缺失时跳过（后端 CI 无前端源码）
            return
        text = fe.read_text(encoding="utf-8")
        assert "'/system/self-check'" in text, "前端调用路径必须与后端 /api/v1/system/self-check 对齐"
