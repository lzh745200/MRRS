"""app.api.v1.messages_extended 覆盖率攻坚测试

直接 async 调用端点函数，MessageService 以 patch.object 替换（协作者），
覆盖全部 6 个端点的正常与异常分支。
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.messages_extended as m

CREATED_AT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
READ_AT = datetime(2024, 1, 2, 8, 30, 0, tzinfo=timezone.utc)


class TestSendMessage:
    async def test_success(self):
        svc = MagicMock()
        svc.send_message.return_value = SimpleNamespace(id=42, created_at=CREATED_AT)
        req = m.SendMessageRequest(receiver_id=7, title="标题", content="内容")
        db = MagicMock()
        with patch.object(m, "MessageService", return_value=svc) as ms:
            result = await m.send_message(request=req, current_user=MagicMock(), db=db)
        assert result == {"message_id": 42, "created_at": CREATED_AT.isoformat()}
        ms.assert_called_once_with(db)
        svc.send_message.assert_called_once_with(
            user_id=7, message_type="system", title="标题", content="内容"
        )

    async def test_approval_type_allowed(self):
        svc = MagicMock()
        svc.send_message.return_value = SimpleNamespace(id=43, created_at=CREATED_AT)
        req = m.SendMessageRequest(receiver_id=8, title="审批", content="请审批", message_type="approval")
        with patch.object(m, "MessageService", return_value=svc):
            result = await m.send_message(request=req, current_user=MagicMock(), db=MagicMock())
        assert result["message_id"] == 43
        svc.send_message.assert_called_once_with(
            user_id=8, message_type="approval", title="审批", content="请审批"
        )

    async def test_invalid_type_400(self):
        req = m.SendMessageRequest(receiver_id=7, title="t", content="c", message_type="private")
        with pytest.raises(HTTPException) as exc_info:
            await m.send_message(request=req, current_user=MagicMock(), db=MagicMock())
        assert exc_info.value.status_code == 400
        assert "不支持的消息类型" in exc_info.value.detail


class TestGetUnreadCount:
    async def test_returns_count(self):
        svc = MagicMock()
        svc.get_unread_count.return_value = 9
        with patch.object(m, "MessageService", return_value=svc):
            result = await m.get_unread_count(current_user=SimpleNamespace(id=5), db=MagicMock())
        assert result == {"unread_count": 9}
        svc.get_unread_count.assert_called_once_with(user_id=5)


class TestGetMessages:
    async def test_list_and_pagination(self):
        msg_unread = SimpleNamespace(
            id=1, title="未读", content="c1", message_type="system",
            is_read=False, read_at=None, created_at=CREATED_AT,
        )
        msg_read = SimpleNamespace(
            id=2, title="已读", content="c2", message_type="task",
            is_read=True, read_at=READ_AT, created_at=CREATED_AT,
        )
        svc = MagicMock()
        svc.get_messages.return_value = {"total": 2, "items": [msg_unread, msg_read]}
        with patch.object(m, "MessageService", return_value=svc):
            result = await m.get_messages(
                message_type="system", is_read=False, limit=10, offset=20,
                current_user=SimpleNamespace(id=5), db=MagicMock(),
            )
        # offset=20 / limit=10 → page=3
        svc.get_messages.assert_called_once_with(
            user_id=5, message_type="system", is_read=False, page=3, page_size=10
        )
        assert result["total"] == 2
        assert [item["id"] for item in result["messages"]] == [1, 2]
        assert result["messages"][0]["read_at"] is None
        assert result["messages"][1]["read_at"] == READ_AT.isoformat()
        assert result["messages"][1]["created_at"] == CREATED_AT.isoformat()
        assert result["messages"][1]["message_type"] == "task"


class TestMarkAsRead:
    async def test_success(self):
        svc = MagicMock()
        svc.mark_as_read.return_value = 1
        with patch.object(m, "MessageService", return_value=svc):
            result = await m.mark_as_read(
                message_id=3, current_user=SimpleNamespace(id=5), db=MagicMock()
            )
        assert result["code"] == 200
        assert result["success"] is True
        assert result["message"] == "已标记为已读"
        svc.mark_as_read.assert_called_once_with(user_id=5, message_ids=[3])

    async def test_not_found_404(self):
        svc = MagicMock()
        svc.mark_as_read.return_value = 0
        with patch.object(m, "MessageService", return_value=svc):
            with pytest.raises(HTTPException) as exc_info:
                await m.mark_as_read(
                    message_id=999, current_user=SimpleNamespace(id=5), db=MagicMock()
                )
        assert exc_info.value.status_code == 404
        assert "消息不存在" in exc_info.value.detail


class TestMarkAllAsRead:
    async def test_success(self):
        svc = MagicMock()
        svc.mark_all_as_read.return_value = 4
        with patch.object(m, "MessageService", return_value=svc):
            result = await m.mark_all_as_read(current_user=SimpleNamespace(id=5), db=MagicMock())
        assert result == {"marked_count": 4}
        svc.mark_all_as_read.assert_called_once_with(user_id=5)


class TestDeleteMessage:
    async def test_success(self):
        svc = MagicMock()
        svc.delete_messages.return_value = 1
        with patch.object(m, "MessageService", return_value=svc):
            result = await m.delete_message(
                message_id=3, current_user=SimpleNamespace(id=5), db=MagicMock()
            )
        assert result["code"] == 200
        assert result["success"] is True
        assert result["message"] == "消息已删除"
        svc.delete_messages.assert_called_once_with(user_id=5, message_ids=[3])

    async def test_not_found_404(self):
        svc = MagicMock()
        svc.delete_messages.return_value = 0
        with patch.object(m, "MessageService", return_value=svc):
            with pytest.raises(HTTPException) as exc_info:
                await m.delete_message(
                    message_id=999, current_user=SimpleNamespace(id=5), db=MagicMock()
                )
        assert exc_info.value.status_code == 404
        assert "消息不存在" in exc_info.value.detail
