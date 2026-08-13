"""通知偏好服务单元测试 (100% coverage)"""
import datetime
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def svc(mock_db):
    from app.services.notification_preference_service import NotificationPreferenceService
    return NotificationPreferenceService(db=mock_db)


class TestInit:
    def test_stores_db(self, svc, mock_db):
        assert svc.db is mock_db


class TestGetPreference:
    def test_returns_existing(self, svc, mock_db):
        pref = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = pref
        assert svc.get_preference(1) is pref

    def test_creates_default_when_not_found(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(svc, '_create_default_preference') as mock_create:
            mock_create.return_value = MagicMock()
            result = svc.get_preference(1)
            mock_create.assert_called_once_with(1)
            assert result is mock_create.return_value


class TestCreateDefaultPreference:
    @patch('app.services.notification_preference_service.NotificationPreference')
    def test_creates_default(self, mock_model, svc, mock_db):
        mock_pref = MagicMock()
        mock_model.return_value = mock_pref
        result = svc._create_default_preference(42)
        assert result is mock_pref
        mock_model.assert_called_once()
        _, kwargs = mock_model.call_args
        assert kwargs['user_id'] == 42
        # 模型真实列
        assert kwargs['site_system'] is True
        assert kwargs['site_approval'] is True
        assert kwargs['site_task'] is True
        assert kwargs['email_system'] is False
        assert kwargs['email_approval'] is True
        assert kwargs['email_task'] is True
        assert kwargs['push_system'] is True
        assert kwargs['push_approval'] is True
        assert kwargs['push_task'] is True
        mock_db.add.assert_called_once_with(mock_pref)
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_pref)


class TestUpdatePreference:
    def test_updates_allowed_fields(self, svc, mock_db):
        pref = MagicMock()
        pref.site_system = True
        pref.email_system = True
        pref.updated_at = None
        svc.get_preference = MagicMock(return_value=pref)
        result = svc.update_preference(
            1,
            site_system=False,
            email_system=False,
        )
        assert result is pref
        assert pref.site_system is False
        assert pref.email_system is False
        assert pref.updated_at is not None
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(pref)

    def test_updates_all_allowed_fields(self, svc, mock_db):
        pref = MagicMock()
        svc.get_preference = MagicMock(return_value=pref)
        svc.update_preference(1, site_system=True, site_approval=True, site_task=True,
                              email_system=True, email_approval=True, email_task=True,
                              push_system=True, push_approval=True, push_task=True)
        assert pref.site_system is True
        assert pref.site_approval is True
        assert pref.site_task is True
        assert pref.email_system is True
        assert pref.email_approval is True
        assert pref.email_task is True
        assert pref.push_system is True
        assert pref.push_approval is True
        assert pref.push_task is True

    def test_ignores_unknown_fields(self, svc, mock_db):
        pref = MagicMock()
        svc.get_preference = MagicMock(return_value=pref)
        svc.update_preference(1, invalid_field="value")
        mock_db.commit.assert_called_once()

    def test_ignores_fields_not_on_preference(self, svc, mock_db):
        pref = MagicMock(spec=[])  # no attributes
        svc.get_preference = MagicMock(return_value=pref)
        svc.update_preference(1, site_message_enabled=False)
        mock_db.commit.assert_called_once()


class TestUpdateSiteMessageSettings:
    def test_delegates(self, svc):
        svc.update_preference = MagicMock()
        result = svc.update_site_message_settings(1, enabled=False, system=False)
        svc.update_preference.assert_called_once_with(
            1,
            site_system=False,
            site_approval=True,
            site_task=True,
        )
        assert result is svc.update_preference.return_value


class TestUpdateEmailSettings:
    def test_delegates(self, svc):
        svc.update_preference = MagicMock()
        result = svc.update_email_settings(1, enabled=False, report=True)
        svc.update_preference.assert_called_once_with(
            1,
            email_system=True,
            email_approval=True,
            email_task=True,
        )
        assert result is svc.update_preference.return_value


class TestUpdateQuietHours:
    def test_compat_no_crash(self, svc, mock_db):
        pref = MagicMock()
        svc.get_preference = MagicMock(return_value=pref)
        result = svc.update_quiet_hours(1, enabled=True, start_time="22:00", end_time="06:00")
        assert result is pref


class TestShouldSendSiteMessage:
    def test_disabled_all(self, svc, mock_db):
        pref = MagicMock(site_system=False, site_approval=False, site_task=False, quiet_hours_enabled=False)
        mock_db.query.return_value.filter.return_value.first.return_value = pref
        assert svc.should_send_site_message(1, "system") is False

    def test_in_quiet_hours(self, svc, mock_db):
        pref = MagicMock(site_system=True, quiet_hours_enabled=True,
                         quiet_hours_start="22:00", quiet_hours_end="06:00")
        mock_db.query.return_value.filter.return_value.first.return_value = pref
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 23, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc.should_send_site_message(1, "system") is False

    @pytest.mark.parametrize("notif_type,attr_val,expected", [
        ("system", True, True),
        ("system", False, False),
        ("approval", True, True),
        ("approval", False, False),
        ("task", True, True),
        ("task", False, False),
        ("report", True, True),
        ("report", False, True),
        ("unknown", None, True),
    ])
    def test_type_mapping(self, svc, mock_db, notif_type, attr_val, expected):
        pref = MagicMock(site_system=True, site_approval=True, site_task=True, quiet_hours_enabled=False)
        if attr_val is not None and notif_type != "report":
            attr_map = {
                "system": "site_system",
                "approval": "site_approval",
                "task": "site_task",
            }
            setattr(pref, attr_map[notif_type], attr_val)
        mock_db.query.return_value.filter.return_value.first.return_value = pref
        assert svc.should_send_site_message(1, notif_type) is expected


class TestShouldSendEmail:
    def test_disabled(self, svc, mock_db):
        pref = MagicMock(email_system=False, email_approval=False, email_task=False, quiet_hours_enabled=False)
        mock_db.query.return_value.filter.return_value.first.return_value = pref
        assert svc.should_send_email(1, "system") is False

    @pytest.mark.parametrize("notif_type,attr_val,expected", [
        ("system", True, True),
        ("system", False, False),
        ("approval", True, True),
        ("approval", False, False),
        ("task", True, True),
        ("task", False, False),
        ("report", True, False),
        ("report", False, False),
        ("unknown", None, False),
    ])
    def test_type_mapping(self, svc, mock_db, notif_type, attr_val, expected):
        pref = MagicMock(email_system=True, email_approval=True, email_task=True, quiet_hours_enabled=False)
        if attr_val is not None and notif_type != "report":
            attr_map = {
                "system": "email_system",
                "approval": "email_approval",
                "task": "email_task",
            }
            setattr(pref, attr_map[notif_type], attr_val)
        mock_db.query.return_value.filter.return_value.first.return_value = pref
        assert svc.should_send_email(1, notif_type) is expected


class TestIsInQuietHours:
    def test_not_enabled(self, svc):
        pref = MagicMock(quiet_hours_enabled=False)
        assert svc._is_in_quiet_hours(pref) is False

    def test_model_without_field(self, svc):
        pref = MagicMock(spec=[])  # 模型无 quiet_hours 列时的行为
        assert svc._is_in_quiet_hours(pref) is False

    def test_no_start_time(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start=None,
                         quiet_hours_end="06:00")
        assert svc._is_in_quiet_hours(pref) is False

    def test_no_end_time(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="22:00",
                         quiet_hours_end=None)
        assert svc._is_in_quiet_hours(pref) is False

    def test_within_same_day(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="09:00",
                         quiet_hours_end="17:00")
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 12, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc._is_in_quiet_hours(pref) is True

    def test_outside_same_day(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="09:00",
                         quiet_hours_end="17:00")
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 20, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc._is_in_quiet_hours(pref) is False

    def test_cross_midnight_within_late(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="22:00",
                         quiet_hours_end="06:00")
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 23, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc._is_in_quiet_hours(pref) is True

    def test_cross_midnight_within_early(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="22:00",
                         quiet_hours_end="06:00")
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 3, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc._is_in_quiet_hours(pref) is True

    def test_cross_midnight_outside(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="22:00",
                         quiet_hours_end="06:00")
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 12, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc._is_in_quiet_hours(pref) is False

    def test_invalid_time_format(self, svc):
        pref = MagicMock(quiet_hours_enabled=True, quiet_hours_start="not-a-time",
                         quiet_hours_end="17:00")
        with patch('app.services.notification_preference_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.datetime(2024, 1, 1, 12, 0)
            mock_dt.strptime = datetime.datetime.strptime
            assert svc._is_in_quiet_hours(pref) is False


class TestGetUsersForNotification:
    def test_site_channel(self, svc):
        svc.should_send_site_message = MagicMock(side_effect=[True, False, True])
        result = svc.get_users_for_notification([1, 2, 3], "system", "site")
        assert result == [1, 3]

    def test_email_channel(self, svc):
        svc.should_send_email = MagicMock(side_effect=[False, True])
        result = svc.get_users_for_notification([10, 20], "task", "email")
        assert result == [20]

    def test_unknown_channel(self, svc):
        result = svc.get_users_for_notification([1, 2, 3], "system", "sms")
        assert result == []

    def test_empty_user_ids(self, svc):
        result = svc.get_users_for_notification([], "system", "site")
        assert result == []


class TestPreferenceToDict:
    def test_with_updated_at(self, svc):
        pref = MagicMock(
            user_id=1,
            site_system=True,
            site_approval=True,
            site_task=True,
            email_system=True,
            email_approval=True,
            email_task=False,
            quiet_hours_enabled=False,
            quiet_hours_start=None,
            quiet_hours_end=None,
            updated_at=datetime.datetime(2024, 1, 1, 12, 0, 0),
        )
        result = svc.preference_to_dict(pref)
        assert result["user_id"] == 1
        assert result["site_message"]["enabled"] is True
        assert result["site_message"]["system"] is True
        assert result["site_message"]["report"] is True
        assert result["email"]["enabled"] is True
        assert result["email"]["task"] is False
        assert result["email"]["report"] is False
        assert result["quiet_hours"]["enabled"] is False
        assert result["quiet_hours"]["start"] is None
        assert result["updated_at"] == "2024-01-01T12:00:00"

    def test_without_updated_at(self, svc):
        pref = MagicMock(
            user_id=2,
            site_system=False,
            site_approval=False,
            site_task=False,
            email_system=False,
            email_approval=False,
            email_task=False,
            updated_at=None,
        )
        result = svc.preference_to_dict(pref)
        assert result["updated_at"] is None
        assert result["site_message"]["enabled"] is False
        assert result["email"]["enabled"] is False
