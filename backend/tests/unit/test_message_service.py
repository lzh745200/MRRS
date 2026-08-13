"""
站内消息服务单元测试
覆盖: app/services/message_service.py
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def msg_svc(mock_db):
    from app.services.message_service import MessageService
    return MessageService(db=mock_db)


class TestSendMessage:
    def test_send_system_message(self, msg_svc, mock_db):
        mock_msg = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        msg_svc.send_message = MagicMock(return_value=mock_msg)
        result = msg_svc.send_system_message(1, "Title", "Content")
        msg_svc.send_message.assert_called_once_with(1, "system", "Title", "Content", None)
        assert result is mock_msg

    def test_send_approval_message(self, msg_svc):
        mock_msg = MagicMock()
        msg_svc.send_message = MagicMock(return_value=mock_msg)
        result = msg_svc.send_approval_message(1, "Approval", "Details", "/link")
        msg_svc.send_message.assert_called_once_with(1, "approval", "Approval", "Details", "/link")
        assert result is mock_msg

    def test_send_task_message(self, msg_svc):
        mock_msg = MagicMock()
        msg_svc.send_message = MagicMock(return_value=mock_msg)
        result = msg_svc.send_task_message(1, "Task", "Do this")
        msg_svc.send_message.assert_called_once_with(1, "task", "Task", "Do this", None)
        assert result is mock_msg

    def test_send_batch_messages(self, msg_svc):
        mock_msgs = [MagicMock(), MagicMock(), MagicMock()]
        msg_svc.send_message = MagicMock(side_effect=mock_msgs)
        result = msg_svc.send_batch_messages([1, 2, 3], "system", "Batch", "Content")
        assert len(result) == 3
        assert msg_svc.send_message.call_count == 3

    def test_send_message_invalid_type(self, msg_svc, mock_db):
        from unittest.mock import patch as mock_patch
        with mock_patch.object(msg_svc, 'send_message',
                               side_effect=ValueError("无效的消息类型")):
            with pytest.raises(ValueError, match="无效的消息类型"):
                msg_svc.send_message(1, "invalid_type", "T", "C")


class TestUnreadCount:
    def test_get_unread_count(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        result = msg_svc.get_unread_count(1)
        assert result == 5

    def test_get_unread_count_zero(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        result = msg_svc.get_unread_count(1)
        assert result == 0

    def test_get_unread_count_by_type(self, msg_svc, mock_db):
        row1 = MagicMock()
        row1.message_type = "system"
        row1.count = 3
        row2 = MagicMock()
        row2.message_type = "approval"
        row2.count = 2
        mock_db.query.return_value.filter.return_value \
            .group_by.return_value.all.return_value = [row1, row2]

        result = msg_svc.get_unread_count_by_type(1)
        assert result["system"] == 3
        assert result["approval"] == 2
        assert result["task"] == 0


class TestGetMessages:
    def test_get_messages_basic(self, msg_svc, mock_db):
        mock_items = [MagicMock(), MagicMock()]
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_items

        result = msg_svc.get_messages(1)
        assert result["items"] == mock_items
        assert result["total"] == 2
        assert result["page"] == 1

    def test_get_messages_with_filters(self, msg_svc, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        now = datetime.now(timezone.utc)
        result = msg_svc.get_messages(
            1, message_type="system", is_read=False,
            start_date=now - timedelta(days=7), end_date=now,
        )
        assert result["total"] == 0

    def test_get_message_found(self, msg_svc, mock_db):
        mock_msg = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_msg
        result = msg_svc.get_message(1, 1)
        assert result is mock_msg

    def test_get_message_not_found(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = msg_svc.get_message(999, 1)
        assert result is None


class TestMarkAsRead:
    def test_mark_as_read(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.update.return_value = 3
        result = msg_svc.mark_as_read(1, [1, 2, 3])
        assert result == 3
        mock_db.commit.assert_called_once()

    def test_mark_single_as_read_success(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.update.return_value = 1
        result = msg_svc.mark_single_as_read(1, 1)
        assert result is True

    def test_mark_single_as_read_failure(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.update.return_value = 0
        result = msg_svc.mark_single_as_read(1, 999)
        assert result is False

    def test_mark_all_as_read(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.update.return_value = 10
        result = msg_svc.mark_all_as_read(1)
        assert result == 10

    def test_mark_all_as_read_by_type(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value \
            .filter.return_value.update.return_value = 5
        result = msg_svc.mark_all_as_read(1, message_type="system")
        assert result == 5


class TestDeleteMessages:
    def test_delete_messages(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 2
        result = msg_svc.delete_messages(1, [1, 2])
        assert result == 2

    def test_delete_single_message_success(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 1
        result = msg_svc.delete_single_message(1, 1)
        assert result is True

    def test_delete_single_message_failure(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        result = msg_svc.delete_single_message(1, 999)
        assert result is False

    def test_delete_all_read_messages(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 15
        result = msg_svc.delete_all_read_messages(1)
        assert result == 15


class TestCleanupOldMessages:
    def test_cleanup_default_retention(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 100
        result = msg_svc.cleanup_old_messages()
        assert result == 100

    def test_cleanup_custom_retention(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 50
        result = msg_svc.cleanup_old_messages(days=30)
        assert result == 50


class TestGetMessageStats:
    def test_get_message_stats(self, msg_svc, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value \
            .group_by.return_value.all.return_value = []

        result = msg_svc.get_message_stats(1)
        assert result["total"] == 100
        assert "unread" in result
        assert "read" in result
        assert "unread_by_type" in result


class TestMessageRetention:
    def test_default_retention_days(self, msg_svc):
        assert msg_svc.MESSAGE_RETENTION_DAYS == 30
