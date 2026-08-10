"""
messages.py 消息通知API覆盖率攻坚测试

策略：dependency_overrides 注入 mock 服务（MessageService / NotificationPreferenceService），
使 handler 真实执行；recent-activities 端点用 mock_db 查询链覆盖全部映射分支与异常分支。
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.v1.messages import (
    get_message_service,
    get_preference_service,
    get_template_service,
)
from app.core.database import get_db
from app.core.security import get_current_user


@pytest.fixture
def mock_user():
    return SimpleNamespace(id=1, username="admin", role="admin", organization_id=1)


@pytest.fixture
def msg_service():
    return MagicMock()


@pytest.fixture
def pref_service():
    return MagicMock()


@pytest.fixture
def authed_client(client, mock_db, mock_user, msg_service, pref_service):
    """注入认证用户 + mock 消息/偏好服务 + mock DB 的客户端"""
    client.app.dependency_overrides[get_db] = lambda: mock_db
    client.app.dependency_overrides[get_current_user] = lambda: mock_user
    client.app.dependency_overrides[get_message_service] = lambda: msg_service
    client.app.dependency_overrides[get_preference_service] = lambda: pref_service
    yield client
    client.app.dependency_overrides.pop(get_message_service, None)
    client.app.dependency_overrides.pop(get_preference_service, None)


def _msg(id=1, is_read=False):
    """构造可通过 MessageResponse.model_validate 的消息对象"""
    return SimpleNamespace(
        id=id,
        message_type="system",
        title=f"标题{id}",
        content="内容",
        link=None,
        is_read=is_read,
        read_at=None,
        created_at=datetime(2026, 7, 1, 12, 0, 0),
    )


# ==================== 消息列表 ====================


class TestGetMessages:
    def test_list_success(self, authed_client, msg_service):
        msg_service.get_messages.return_value = {
            "items": [_msg(1), _msg(2)],
            "total": 2,
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
        }
        resp = authed_client.get("/api/v1/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "标题1"

    def test_list_with_all_filters(self, authed_client, msg_service, mock_user):
        msg_service.get_messages.return_value = {
            "items": [],
            "total": 0,
            "page": 2,
            "page_size": 5,
            "total_pages": 0,
        }
        resp = authed_client.get(
            "/api/v1/messages?message_type=approval&is_read=true"
            "&start_date=2026-07-01&end_date=2026-07-24&page=2&page_size=5"
        )
        assert resp.status_code == 200
        kwargs = msg_service.get_messages.call_args.kwargs
        assert kwargs["user_id"] == mock_user.id
        assert kwargs["message_type"] == "approval"
        assert kwargs["is_read"] is True
        assert kwargs["start_date"] == datetime(2026, 7, 1)
        assert kwargs["end_date"] == datetime(2026, 7, 24)
        assert kwargs["page"] == 2 and kwargs["page_size"] == 5

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2026-07-24T10:20:30", datetime(2026, 7, 24, 10, 20, 30)),
            ("2026-07-24T10:20", datetime(2026, 7, 24, 10, 20)),
            ("2026-07-24 10:20:30", datetime(2026, 7, 24, 10, 20, 30)),
            ("2026-07-24", datetime(2026, 7, 24)),
            ("not-a-date", None),
            ("", None),
            ("   ", None),
        ],
    )
    def test_parse_query_date_formats(self, authed_client, msg_service, raw, expected):
        msg_service.get_messages.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
        }
        resp = authed_client.get(f"/api/v1/messages?start_date={raw}")
        assert resp.status_code == 200
        assert msg_service.get_messages.call_args.kwargs["start_date"] == expected

    def test_list_page_validation(self, authed_client):
        resp = authed_client.get("/api/v1/messages?page=0")
        assert resp.status_code == 422
        resp = authed_client.get("/api/v1/messages?page_size=501")
        assert resp.status_code == 422


# ==================== 未读数量 ====================


class TestUnreadCount:
    def test_unread_count(self, authed_client, msg_service, mock_user):
        msg_service.get_unread_count.return_value = 7
        msg_service.get_unread_count_by_type.return_value = {"system": 5, "task": 2}
        resp = authed_client.get("/api/v1/messages/unread-count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        assert data["by_type"] == {"system": 5, "task": 2}
        msg_service.get_unread_count.assert_called_once_with(mock_user.id)
        msg_service.get_unread_count_by_type.assert_called_once_with(mock_user.id)


# ==================== 标记已读 ====================


class TestMarkRead:
    def test_mark_read(self, authed_client, msg_service, mock_user):
        msg_service.mark_as_read.return_value = 3
        resp = authed_client.post("/api/v1/messages/mark-read", json={"message_ids": [1, 2, 3]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        assert "3" in data["message"]
        msg_service.mark_as_read.assert_called_once_with(mock_user.id, [1, 2, 3])

    def test_mark_read_empty_ids_422(self, authed_client):
        resp = authed_client.post("/api/v1/messages/mark-read", json={"message_ids": []})
        assert resp.status_code == 422

    def test_mark_all_read_with_type(self, authed_client, msg_service, mock_user):
        msg_service.mark_all_as_read.return_value = 9
        resp = authed_client.post("/api/v1/messages/mark-all-read?message_type=task")
        assert resp.status_code == 200
        assert resp.json()["count"] == 9
        msg_service.mark_all_as_read.assert_called_once_with(mock_user.id, "task")

    def test_mark_all_read_no_type(self, authed_client, msg_service, mock_user):
        msg_service.mark_all_as_read.return_value = 4
        resp = authed_client.post("/api/v1/messages/mark-all-read")
        assert resp.status_code == 200
        msg_service.mark_all_as_read.assert_called_once_with(mock_user.id, None)


# ==================== 删除消息 ====================


class TestDeleteMessages:
    def test_delete_messages(self, authed_client, msg_service, mock_user):
        msg_service.delete_messages.return_value = 2
        resp = authed_client.request("DELETE", "/api/v1/messages", json={"message_ids": [5, 6]})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        msg_service.delete_messages.assert_called_once_with(mock_user.id, [5, 6])

    def test_delete_messages_empty_ids_422(self, authed_client):
        resp = authed_client.request("DELETE", "/api/v1/messages", json={"message_ids": []})
        assert resp.status_code == 422

    def test_delete_all_read(self, authed_client, msg_service, mock_user):
        msg_service.delete_all_read_messages.return_value = 11
        resp = authed_client.delete("/api/v1/messages/read")
        assert resp.status_code == 200
        assert "11" in resp.json()["message"]
        msg_service.delete_all_read_messages.assert_called_once_with(mock_user.id)


# ==================== 统计 ====================


class TestMessageStats:
    def test_stats_summary(self, authed_client, msg_service, mock_user):
        msg_service.get_message_stats.return_value = {"total": 100, "unread": 7}
        resp = authed_client.get("/api/v1/messages/stats/summary")
        assert resp.status_code == 200
        assert resp.json() == {"total": 100, "unread": 7}
        msg_service.get_message_stats.assert_called_once_with(mock_user.id)


# ==================== 近期动态 ====================


def _audit_log(**kw):
    base = dict(
        id=1,
        action="create",
        status="success",
        resource_type="project",
        resource_id=42,
        username="admin",
        created_at=datetime(2026, 7, 24, 10, 30),
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestRecentActivities:
    def _setup_chain(self, mock_db, logs):
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = logs
        # conftest mock_db.query 是普通函数，须整体替换为 MagicMock 才能控制返回值
        mock_db.query = MagicMock(return_value=chain)

    def test_activities_full_mapping(self, authed_client, mock_db):
        self._setup_chain(mock_db, [_audit_log()])
        resp = authed_client.get("/api/v1/messages/recent-activities?limit=5")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        item = data["items"][0]
        assert item["title"] == "帮扶项目新增记录"
        assert item["type"] == "success"
        assert "admin" in item["description"]
        assert "ID: 42" in item["description"]
        assert item["time"] == "2026-07-24 10:30"

    def test_activities_fallbacks(self, authed_client, mock_db):
        """action=None→update、未知资源类型原样、username=None→系统、created_at=None→空时间"""
        self._setup_chain(
            mock_db,
            [
                _audit_log(
                    id=2,
                    action=None,
                    resource_type="unknown_type",
                    resource_id=None,
                    username=None,
                    created_at=None,
                )
            ],
        )
        resp = authed_client.get("/api/v1/messages/recent-activities")
        assert resp.status_code == 200
        item = resp.json()["data"]["items"][0]
        assert item["title"] == "unknown_type更新数据"
        assert item["type"] == "info"
        assert "系统" in item["description"]
        assert "ID:" not in item["description"]
        assert item["time"] == ""

    def test_activities_known_actions_and_empty(self, authed_client, mock_db):
        self._setup_chain(mock_db, [])
        resp = authed_client.get("/api/v1/messages/recent-activities")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == [] and data["total"] == 0

    def test_activities_operational_error(self, authed_client, mock_db):
        from sqlalchemy.exc import OperationalError

        mock_db.query = MagicMock(side_effect=OperationalError("SELECT 1", {}, Exception("db down")))
        resp = authed_client.get("/api/v1/messages/recent-activities")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_activities_programming_error(self, authed_client, mock_db):
        from sqlalchemy.exc import ProgrammingError

        mock_db.query = MagicMock(side_effect=ProgrammingError("SELECT 1", {}, Exception("no table")))
        resp = authed_client.get("/api/v1/messages/recent-activities")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_activities_unexpected_error_500(self, authed_client, mock_db):
        mock_db.query = MagicMock(side_effect=RuntimeError("boom"))
        resp = authed_client.get("/api/v1/messages/recent-activities")
        assert resp.status_code == 500
        assert "RuntimeError" in resp.json()["detail"]

    def test_activities_limit_validation(self, authed_client):
        resp = authed_client.get("/api/v1/messages/recent-activities?limit=0")
        assert resp.status_code == 422
        resp = authed_client.get("/api/v1/messages/recent-activities?limit=51")
        assert resp.status_code == 422


# ==================== 单条消息 ====================


class TestGetMessage:
    def test_get_message_auto_mark_read(self, authed_client, msg_service, mock_user):
        msg_service.get_message.return_value = _msg(9, is_read=False)
        resp = authed_client.get("/api/v1/messages/9")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 9
        assert data["is_read"] is True
        msg_service.get_message.assert_called_once_with(9, mock_user.id)
        msg_service.mark_single_as_read.assert_called_once_with(mock_user.id, 9)

    def test_get_message_already_read_no_mark(self, authed_client, msg_service):
        msg_service.get_message.return_value = _msg(3, is_read=True)
        resp = authed_client.get("/api/v1/messages/3")
        assert resp.status_code == 200
        msg_service.mark_single_as_read.assert_not_called()

    def test_get_message_not_found(self, authed_client, msg_service):
        msg_service.get_message.return_value = None
        resp = authed_client.get("/api/v1/messages/404")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "消息不存在"


# ==================== 通知偏好 ====================


class TestNotificationPreferences:
    def _pref_result(self):
        return {
            "user_id": 1,
            "site_message": {"enabled": True, "system": True, "approval": False, "task": True},
            "email": {"enabled": True, "system": False, "approval": True, "task": False},
            "quiet_hours": {},
        }

    def test_get_preferences_flat_fields(self, authed_client, pref_service, mock_user):
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = self._pref_result()
        resp = authed_client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        # 扁平字段由嵌套结构映射
        assert data["site_system"] is True
        assert data["site_approval"] is False
        assert data["site_task"] is True
        assert data["email_system"] is False
        assert data["email_approval"] is True
        assert data["email_task"] is False
        pref_service.get_preference.assert_called_once_with(mock_user.id)

    def test_get_preferences_default_true_when_missing(self, authed_client, pref_service):
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = {
            "user_id": 1,
            "site_message": {},
            "email": {},
            "quiet_hours": {},
        }
        resp = authed_client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_system"] is True and data["email_task"] is True

    def test_update_preferences_partial(self, authed_client, pref_service, mock_user):
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.side_effect = [
            self._pref_result(),  # 更新前读取
            self._pref_result(),  # 更新后返回
        ]
        resp = authed_client.put(
            "/api/v1/notifications/preferences",
            json={"site_system": False, "email_task": True},
        )
        assert resp.status_code == 200
        site_call = pref_service.update_site_message_settings.call_args.kwargs
        email_call = pref_service.update_email_settings.call_args.kwargs
        assert site_call["user_id"] == mock_user.id
        assert site_call["system"] is False  # 被更新
        assert site_call["approval"] is False  # 保留原值
        assert email_call["task"] is True  # 被更新
        assert email_call["system"] is False  # 保留原值

    def test_update_preferences_none_fields_skipped(self, authed_client, pref_service):
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.side_effect = [self._pref_result(), self._pref_result()]
        resp = authed_client.put("/api/v1/notifications/preferences", json={})
        assert resp.status_code == 200
        site_call = pref_service.update_site_message_settings.call_args.kwargs
        assert site_call["system"] is True  # 原值保留

    def test_update_preferences_remaining_flags(self, authed_client, pref_service):
        """覆盖 site_approval/site_task/email_system/email_approval 四个更新分支"""
        pref_service.get_preference.return_value = MagicMock()
        pref_service.preference_to_dict.side_effect = [self._pref_result(), self._pref_result()]
        resp = authed_client.put(
            "/api/v1/notifications/preferences",
            json={"site_approval": True, "site_task": False, "email_system": True, "email_approval": False},
        )
        assert resp.status_code == 200
        site_call = pref_service.update_site_message_settings.call_args.kwargs
        email_call = pref_service.update_email_settings.call_args.kwargs
        assert site_call["approval"] is True
        assert site_call["task"] is False
        assert email_call["system"] is True
        assert email_call["approval"] is False

    def test_update_site_message_settings(self, authed_client, pref_service, mock_user):
        pref_service.update_site_message_settings.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = {"ok": True}
        resp = authed_client.put(
            "/api/v1/notifications/preferences/site-message",
            json={"enabled": False, "system": False, "approval": True, "task": True, "report": False},
        )
        assert resp.status_code == 200
        pref_service.update_site_message_settings.assert_called_once_with(
            user_id=mock_user.id, enabled=False, system=False, approval=True, task=True, report=False
        )

    def test_update_email_settings(self, authed_client, pref_service, mock_user):
        pref_service.update_email_settings.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = {"ok": True}
        resp = authed_client.put(
            "/api/v1/notifications/preferences/email",
            json={"enabled": True, "system": True, "approval": False, "task": True, "report": True},
        )
        assert resp.status_code == 200
        pref_service.update_email_settings.assert_called_once_with(
            user_id=mock_user.id, enabled=True, system=True, approval=False, task=True, report=True
        )

    def test_update_quiet_hours(self, authed_client, pref_service, mock_user):
        pref_service.update_quiet_hours.return_value = MagicMock()
        pref_service.preference_to_dict.return_value = {"ok": True}
        resp = authed_client.put(
            "/api/v1/notifications/preferences/quiet-hours",
            json={"enabled": True, "start_time": "22:00", "end_time": "07:00"},
        )
        assert resp.status_code == 200
        pref_service.update_quiet_hours.assert_called_once_with(
            user_id=mock_user.id, enabled=True, start_time="22:00", end_time="07:00"
        )


# ==================== 依赖注入工厂 ====================


class TestDependencyFactories:
    def test_get_template_service(self, mock_db):
        from app.services.message_template_service import MessageTemplateService

        svc = get_template_service(mock_db)
        assert isinstance(svc, MessageTemplateService)

    def test_get_message_service(self, mock_db):
        from app.services.message_service import MessageService

        svc = get_message_service(mock_db)
        assert isinstance(svc, MessageService)

    def test_get_preference_service(self, mock_db):
        from app.services.notification_preference_service import NotificationPreferenceService

        svc = get_preference_service(mock_db)
        assert isinstance(svc, NotificationPreferenceService)
