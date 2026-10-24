"""邮件通知偏好必须如实标识「离线不可用」通道。

背景（离线适配审计 A11）：后端只有 alert_service 的 SMTP 告警一个发送方，
通知偏好里的 email_* 开关没有任何消费者 —— 用户在偏好页开启"邮件通知"后
永远收不到邮件。故 GET /preferences 与 PUT /preferences/email（及统一 PUT）
的响应统一追加 ``emailChannel: "unavailable_offline"``，且不破坏既有字段。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.v1.messages import get_preference_service
from app.core.database import get_db
from app.core.security import get_current_user

EMAIL_CHANNEL_UNAVAILABLE = "unavailable_offline"


@pytest.fixture
def mock_user():
    return SimpleNamespace(id=1, username="admin", role="admin", organization_id=1)


@pytest.fixture
def pref_service():
    return MagicMock()


@pytest.fixture
def authed_client(client, mock_db, mock_user, pref_service):
    client.app.dependency_overrides[get_db] = lambda: mock_db
    client.app.dependency_overrides[get_current_user] = lambda: mock_user
    client.app.dependency_overrides[get_preference_service] = lambda: pref_service
    yield client
    client.app.dependency_overrides.pop(get_preference_service, None)


def _pref_dict():
    return {
        "site_message": {"enabled": True, "system": True, "approval": True, "task": True},
        "email": {"enabled": True, "system": True, "approval": True, "task": True},
        "quiet_hours": {"enabled": False, "start_time": None, "end_time": None},
    }


class TestEmailChannelFlag:
    def test_get_preferences_flags_email_channel_unavailable(self, authed_client, pref_service):
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = _pref_dict()

        resp = authed_client.get("/api/v1/notifications/preferences")

        assert resp.status_code == 200
        body = resp.json()
        assert body["emailChannel"] == EMAIL_CHANNEL_UNAVAILABLE
        # 既有字段不受影响
        assert body["email_system"] is True
        assert body["email"]["enabled"] is True

    def test_update_email_preferences_flags_channel(self, authed_client, pref_service):
        pref_service.update_email_settings.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = _pref_dict()

        resp = authed_client.put(
            "/api/v1/notifications/preferences/email",
            json={"enabled": True, "system": True, "approval": False, "task": True, "report": True},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["emailChannel"] == EMAIL_CHANNEL_UNAVAILABLE
        # 既有响应字段保持不变（不破坏契约）
        assert body["email"]["system"] is True
        assert body["site_message"]["enabled"] is True
        pref_service.update_email_settings.assert_called_once_with(
            user_id=1, enabled=True, system=True, approval=False, task=True, report=True
        )

    def test_unified_update_flags_channel(self, authed_client, pref_service):
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = _pref_dict()

        resp = authed_client.put(
            "/api/v1/notifications/preferences",
            json={"email_system": False},
        )

        assert resp.status_code == 200
        assert resp.json()["emailChannel"] == EMAIL_CHANNEL_UNAVAILABLE
