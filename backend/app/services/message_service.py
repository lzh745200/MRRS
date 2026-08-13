"""
站内消息服务

Task 7.3: 实现站内消息服务
- 消息发送（系统 / 审批 / 任务三种类型）
- 未读消息计数
- 消息列表查询（支持类型和时间筛选）
- 标记已读功能
- 批量删除功能

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

from datetime import timezone, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.message import Message, MessageType
from app.core.transaction import safe_commit


class MessageService:
    """
    站内消息服务类

    Requirements:
    - 5.1: 支持发送系统通知、审批通知、任务提醒三种消息类型
    - 5.2: 显示未读消息数量
    - 5.3: 提供消息列表页面，支持按类型和时间筛选
    - 5.4: 标记消息为已读
    - 5.5: 支持批量标记消息为已读或删除
    """

    # 消息保留天数
    MESSAGE_RETENTION_DAYS = 30

    def __init__(self, db: Session):
        self.db = db

    # ==================== 消息发送 ====================

    def send_message(
        self,
        user_id: int,
        message_type: str,
        title: str,
        content: str,
        link: Optional[str] = None,
    ) -> Message:
        """
        发送站内消息

        Requirements: 5.1 - 支持发送系统通知、审批通知、任务提醒三种消息类型

        Args:
            user_id: 接收用户ID
            message_type: 消息类型 (system / approval / task)
            title: 消息标题
            content: 消息内容
            link: 关联链接（可选）

        Returns:
            Message: 创建的消息对象

        Raises:
            ValueError: 消息类型无效
        """
        # 验证消息类型
        valid_types = [
            MessageType.SYSTEM.value,
            MessageType.APPROVAL.value,
            MessageType.TASK.value,
        ]
        if message_type not in valid_types:
            raise ValueError(f"无效的消息类型: {message_type}，有效类型: {valid_types}")

        message = Message(
            user_id=user_id,
            message_type=message_type,
            title=title,
            content=content,
            link=link,
            is_read=False,
        )

        self.db.add(message)
        safe_commit(self.db)
        self.db.refresh(message)
        return message

    def send_system_message(self, user_id: int, title: str, content: str, link: Optional[str] = None) -> Message:
        """发送系统消息"""
        return self.send_message(user_id, MessageType.SYSTEM.value, title, content, link)

    def send_approval_message(self, user_id: int, title: str, content: str, link: Optional[str] = None) -> Message:
        """发送审批消息"""
        return self.send_message(user_id, MessageType.APPROVAL.value, title, content, link)

    def send_task_message(self, user_id: int, title: str, content: str, link: Optional[str] = None) -> Message:
        """发送任务消息"""
        return self.send_message(user_id, MessageType.TASK.value, title, content, link)

    def send_batch_messages(
        self,
        user_ids: List[int],
        message_type: str,
        title: str,
        content: str,
        link: Optional[str] = None,
    ) -> List[Message]:
        """
        批量发送消息给多个用户

        Args:
            user_ids: 接收用户ID列表
            message_type: 消息类型
            title: 消息标题
            content: 消息内容
            link: 关联链接

        Returns:
            List[Message]: 创建的消息列表
        """
        messages = []
        for user_id in user_ids:
            message = self.send_message(user_id, message_type, title, content, link)
            messages.append(message)
        return messages

    # ==================== 未读消息计数 ====================

    def get_unread_count(self, user_id: int) -> int:
        """
        获取未读消息数量

        Requirements: 5.2 - 显示未读消息数量

        Args:
            user_id: 用户ID

        Returns:
            int: 未读消息数量
        """
        return (
            self.db.query(Message)
            .filter(and_(Message.user_id == user_id, Message.is_read == False))  # noqa: E712
            .count()
        )

    def get_unread_count_by_type(self, user_id: int) -> Dict[str, int]:
        """
        按类型获取未读消息数量

        Args:
            user_id: 用户ID

        Returns:
            Dict[str, int]: 各类型未读消息数量
        """
        result = (
            self.db.query(Message.message_type, func.count(Message.id).label("count"))
            .filter(and_(Message.user_id == user_id, Message.is_read == False))  # noqa: E712
            .group_by(Message.message_type)
            .all()
        )

        counts = {
            MessageType.SYSTEM.value: 0,
            MessageType.APPROVAL.value: 0,
            MessageType.TASK.value: 0,
        }
        for row in result:
            counts[row.message_type] = row.count

        return counts

    # ==================== 消息列表查询 ====================

    def get_messages(
        self,
        user_id: int,
        message_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取消息列表

        Requirements: 5.3 - 提供消息列表页面，支持按类型和时间筛选

        Args:
            user_id: 用户ID
            message_type: 消息类型筛选
            is_read: 已读状态筛选
            start_date: 开始时间
            end_date: 结束时间
            page: 页码
            page_size: 每页数量

        Returns:
            Dict[str, Any]: 包含items, total, page, page_size
        """
        query = self.db.query(Message).filter(Message.user_id == user_id)

        # 类型筛选
        if message_type:
            query = query.filter(Message.message_type == message_type)

        # 已读状态筛选
        if is_read is not None:
            query = query.filter(Message.is_read == is_read)

        # 时间筛选
        if start_date:
            query = query.filter(Message.created_at >= start_date)
        if end_date:
            query = query.filter(Message.created_at <= end_date)

        # 获取总数
        total = query.count()

        # 分页和排序
        offset = (page - 1) * page_size
        items = query.order_by(desc(Message.created_at)).offset(offset).limit(page_size).all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def get_message(self, message_id: int, user_id: int) -> Optional[Message]:
        """
        获取单条消息

        Args:
            message_id: 消息ID
            user_id: 用户ID（用于权限验证）

        Returns:
            Optional[Message]: 消息对象，不存在或无权限返回None
        """
        return self.db.query(Message).filter(and_(Message.id == message_id, Message.user_id == user_id)).first()

    # ==================== 标记已读 ====================

    def mark_as_read(self, user_id: int, message_ids: List[int]) -> int:
        """
        标记消息为已读

        Requirements: 5.4 - 标记消息为已读
        Requirements: 5.5 - 支持批量标记消息为已读

        Args:
            user_id: 用户ID
            message_ids: 消息ID列表

        Returns:
            int: 更新的消息数量
        """
        now = datetime.now(timezone.utc)
        result = (
            self.db.query(Message)
            .filter(
                and_(
                    Message.id.in_(message_ids),
                    Message.user_id == user_id,
                    Message.is_read == False,  # noqa: E712
                )
            )
            .update({"is_read": True, "read_at": now}, synchronize_session=False)
        )
        safe_commit(self.db)
        return result

    def mark_single_as_read(self, user_id: int, message_id: int) -> bool:
        """
        标记单条消息为已读

        Args:
            user_id: 用户ID
            message_id: 消息ID

        Returns:
            bool: 是否成功
        """
        count = self.mark_as_read(user_id, [message_id])
        return count > 0

    def mark_all_as_read(self, user_id: int, message_type: Optional[str] = None) -> int:
        """
        标记所有消息为已读

        Args:
            user_id: 用户ID
            message_type: 消息类型（可选，不指定则标记所有类型）

        Returns:
            int: 更新的消息数量
        """
        now = datetime.now(timezone.utc)
        query = self.db.query(Message).filter(and_(Message.user_id == user_id, Message.is_read == False))  # noqa: E712

        if message_type:
            query = query.filter(Message.message_type == message_type)

        result = query.update({"is_read": True, "read_at": now}, synchronize_session=False)
        safe_commit(self.db)
        return result

    # ==================== 删除消息 ====================

    def delete_messages(self, user_id: int, message_ids: List[int]) -> int:
        """
        批量删除消息

        Requirements: 5.5 - 支持批量删除

        Args:
            user_id: 用户ID
            message_ids: 消息ID列表

        Returns:
            int: 删除的消息数量
        """
        result = (
            self.db.query(Message)
            .filter(and_(Message.id.in_(message_ids), Message.user_id == user_id))
            .delete(synchronize_session=False)
        )
        safe_commit(self.db)
        return result

    def delete_single_message(self, user_id: int, message_id: int) -> bool:
        """
        删除单条消息

        Args:
            user_id: 用户ID
            message_id: 消息ID

        Returns:
            bool: 是否成功
        """
        count = self.delete_messages(user_id, [message_id])
        return count > 0

    def delete_all_read_messages(self, user_id: int) -> int:
        """
        删除所有已读消息

        Args:
            user_id: 用户ID

        Returns:
            int: 删除的消息数量
        """
        result = (
            self.db.query(Message)
            .filter(and_(Message.user_id == user_id, Message.is_read == True))  # noqa: E712
            .delete(synchronize_session=False)
        )
        safe_commit(self.db)
        return result

    # ==================== 消息清理 ====================

    def cleanup_old_messages(self, days: Optional[int] = None) -> int:
        """
        清理过期消息

        Requirements: 5.6 - 保留消息记录90天

        Args:
            days: 保留天数，默认90天

        Returns:
            int: 删除的消息数量
        """
        retention_days = days or self.MESSAGE_RETENTION_DAYS
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        result = self.db.query(Message).filter(Message.created_at < cutoff_date).delete(synchronize_session=False)
        safe_commit(self.db)
        return result

    # ==================== 统计信息 ====================

    def get_message_stats(self, user_id: int) -> Dict[str, Any]:
        """
        获取消息统计信息

        Args:
            user_id: 用户ID

        Returns:
            Dict[str, Any]: 统计信息
        """
        total = self.db.query(Message).filter(Message.user_id == user_id).count()
        unread = self.get_unread_count(user_id)
        unread_by_type = self.get_unread_count_by_type(user_id)

        return {
            "total": total,
            "unread": unread,
            "read": total - unread,
            "unread_by_type": unread_by_type,
        }
