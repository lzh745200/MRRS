"""generate-now 端点测试：属主 200 / 非属主 404 / 管理员可代生成 / 禁用 400。

复用 test_data_reports_api_2.py 的 client fixture 范式（内存库 + dependency_overrides）。
"""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_settings():
    import os
    os.environ["SECRET_KEY"] = "test-secret-key-32-chars-long!!!!!"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    os.environ["CSRF_ENABLED"] = "false"
    from app.core.config import settings
    settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
    settings.ENVIRONMENT = "testing"
    settings.DEBUG = True
    settings.DATABASE_URL = "sqlite:///./test.db"
    settings.CSRF_ENABLED = False
    yield
    for k in ["SECRET_KEY", "ENVIRONMENT", "DEBUG", "DATABASE_URL", "CSRF_ENABLED"]:
        os.environ.pop(k, None)


def _make_app_and_db():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    return app, db, get_current_user, _original_overrides


def _mksub(db, user_id=1, is_active=True, **kw):
    from app.models.supported_village import ReportSubscription

    sub = ReportSubscription(
        user_id=user_id,
        name=kw.get("name", "测试订阅"),
        report_type="comprehensive",
        format="xlsx",
        frequency="daily",
        send_time="08:00",
        is_active=is_active,
    )
    db.add(sub)
    db.commit()
    return sub


class TestGenerateNow:
    def test_owner_generates_success(self, monkeypatch, tmp_path):
        app, db, get_current_user, overrides = _make_app_and_db()
        try:
            user = Mock(id=1, username="owner", role="user", is_superuser=False, is_active=True)
            app.dependency_overrides[get_current_user] = lambda: user
            sub = _mksub(db, user_id=1)
            db.sub = sub

            async def fake_generate(self, db_, sub_, user_, now):
                sub_.last_sent_at = now
                return {"file_name": "f.xlsx", "file_path": str(tmp_path / "f.xlsx"), "size": 3}

            with patch(
                "app.services.subscription_dispatch_service.SubscriptionDispatchService."
                "generate_for_subscription",
                new=fake_generate,
            ):
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.post(f"/api/v1/reports/subscriptions/{sub.id}/generate-now")

            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 200
            assert body["data"]["file_name"] == "f.xlsx"
        finally:
            app.dependency_overrides = overrides
            db.close()
            db.engine.dispose() if hasattr(db, "engine") else None

    def test_non_owner_gets_404(self):
        app, db, get_current_user, overrides = _make_app_and_db()
        try:
            user = Mock(id=2, username="other", role="user", is_superuser=False, is_active=True)
            app.dependency_overrides[get_current_user] = lambda: user
            sub = _mksub(db, user_id=1)  # 属主是 1，当前用户是 2

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(f"/api/v1/reports/subscriptions/{sub.id}/generate-now")

            # 非属主按「订阅不存在」处理（不泄露他人生存状态）
            assert resp.status_code == 404
        finally:
            app.dependency_overrides = overrides
            db.close()

    def test_admin_can_generate_for_others(self, monkeypatch, tmp_path):
        app, db, get_current_user, overrides = _make_app_and_db()
        try:
            admin = Mock(id=99, username="admin", role="admin", is_superuser=False, is_active=True)
            app.dependency_overrides[get_current_user] = lambda: admin
            sub = _mksub(db, user_id=1)

            async def fake_generate(self, db_, sub_, user_, now):
                return {"file_name": "f.xlsx", "file_path": str(tmp_path / "f.xlsx"), "size": 3}

            with patch(
                "app.services.subscription_dispatch_service.SubscriptionDispatchService."
                "generate_for_subscription",
                new=fake_generate,
            ):
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.post(f"/api/v1/reports/subscriptions/{sub.id}/generate-now")

            assert resp.status_code == 200, resp.text
        finally:
            app.dependency_overrides = overrides
            db.close()

    def test_inactive_subscription_400(self):
        app, db, get_current_user, overrides = _make_app_and_db()
        try:
            user = Mock(id=1, username="owner", role="user", is_superuser=False, is_active=True)
            app.dependency_overrides[get_current_user] = lambda: user
            sub = _mksub(db, user_id=1, is_active=False)

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(f"/api/v1/reports/subscriptions/{sub.id}/generate-now")

            assert resp.status_code == 400
            assert "已禁用" in resp.json()["detail"]
        finally:
            app.dependency_overrides = overrides
            db.close()
