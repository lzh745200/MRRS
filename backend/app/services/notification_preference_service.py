"""
通知偏好服务

任务 7.7: 实现通知偏好服务
- 用户通知偏好CRUD
- 根据偏好过滤通知发送

需求: 6.2

注意: 本服务适配 NotificationPreference 模型的真实列
(email_approval/email_task/email_system/site_approval/site_task/site_system/
push_approval/push_task/push_system)。
API 层使用的 site_message.enabled / email.enabled / report / quiet_hours 等
扩展概念在模型无对应列时提供合理默认值（聚合或 False/None），不落库。
"""

from datetime import timezone, datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference
from app.core.transaction import safe_commit


class NotificationPreferenceService:
    """
    通知偏好服务类

    需求:
    - 6.2: 用户可配置接收哪些类型的通知
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== 获取偏好 ====================

    def get_preference(self, user_id: int) -> NotificationPreference:
        """
        获取用户通知偏好

        如果不存在则创建默认偏好

        参数:
            user_id: 用户ID

        返回:
            NotificationPreference: 通知偏好对象
        """
        preference = self.db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()

        if not preference:
            # 创建默认偏好
            preference = self._create_default_preference(user_id)

        return preference

    def _create_default_preference(self, user_id: int) -> NotificationPreference:
        """创建默认通知偏好（使用模型真实列）"""
        preference = NotificationPreference(
            user_id=user_id,
            # 邮件通知默认: 审批/任务开启, 系统关闭（与模型 default 一致）
            email_approval=True,
            email_task=True,
            email_system=False,
            # 站内消息默认全部启用
            site_approval=True,
            site_task=True,
            site_system=True,
            # 实时推送默认全部启用
            push_approval=True,
            push_task=True,
            push_system=True,
        )

        self.db.add(preference)
        safe_commit(self.db)
        self.db.refresh(preference)

        return preference

    # ==================== 更新偏好 ====================

    def update_preference(self, user_id: int, **kwargs) -> NotificationPreference:
        """
        更新用户通知偏好

        参数:
            user_id: 用户ID
            **kwargs: 要更新的字段（仅模型真实列生效）

        返回:
            NotificationPreference: 更新后的偏好对象
        """
        preference = self.get_preference(user_id)

        # 允许更新的字段（模型真实列）
        allowed_fields = [
            "email_approval",
            "email_task",
            "email_system",
            "site_approval",
            "site_task",
            "site_system",
            "push_approval",
            "push_task",
            "push_system",
        ]

        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(preference, field):
                setattr(preference, field, value)

        preference.updated_at = datetime.now(timezone.utc)
        safe_commit(self.db)
        self.db.refresh(preference)

        return preference

    def update_site_message_settings(
        self,
        user_id: int,
        enabled: bool = True,
        system: bool = True,
        approval: bool = True,
        task: bool = True,
        report: bool = True,
    ) -> NotificationPreference:
        """更新站内消息设置（enabled/report 无对应列，仅更新子开关）"""
        return self.update_preference(
            user_id,
            site_system=system,
            site_approval=approval,
            site_task=task,
        )

    def update_email_settings(
        self,
        user_id: int,
        enabled: bool = True,
        system: bool = True,
        approval: bool = True,
        task: bool = True,
        report: bool = False,
    ) -> NotificationPreference:
        """更新邮件通知设置（enabled/report 无对应列，仅更新子开关）"""
        return self.update_preference(
            user_id,
            email_system=system,
            email_approval=approval,
            email_task=task,
        )

    def update_quiet_hours(
        self,
        user_id: int,
        enabled: bool,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> NotificationPreference:
        """更新免打扰时段设置（模型无对应列，调用保持兼容但不持久化）"""
        return self.get_preference(user_id)

    # ==================== 检查偏好 ====================

    def should_send_site_message(self, user_id: int, notification_type: str) -> bool:
        """
        检查是否应该发送站内消息

        参数:
            user_id: 用户ID
            notification_type: 通知类型 (system / approval / task / report)

        返回:
            bool: 是否应该发送
        """
        preference = self.get_preference(user_id)

        # 检查免打扰时段（模型无此配置时返回 False）
        if self._is_in_quiet_hours(preference):
            return False

        # 检查具体类型（report 无对应列，默认放行）
        type_mapping = {
            "system": preference.site_system,
            "approval": preference.site_approval,
            "task": preference.site_task,
            "report": True,
        }

        return type_mapping.get(notification_type, True)

    def should_send_email(self, user_id: int, notification_type: str) -> bool:
        """
        检查是否应该发送邮件

        参数:
            user_id: 用户ID
            notification_type: 通知类型 (system / approval / task / report)

        返回:
            bool: 是否应该发送
        """
        preference = self.get_preference(user_id)

        # 检查具体类型（report 无对应列，默认关闭）
        type_mapping = {
            "system": preference.email_system,
            "approval": preference.email_approval,
            "task": preference.email_task,
            "report": False,
        }

        return type_mapping.get(notification_type, False)

    def _is_in_quiet_hours(self, preference: NotificationPreference) -> bool:
        """检查当前是否在免打扰时段（模型无对应列时恒为 False）"""
        if not getattr(preference, "quiet_hours_enabled", False):
            return False

        start_time = getattr(preference, "quiet_hours_start", None)
        end_time = getattr(preference, "quiet_hours_end", None)

        if not start_time or not end_time:
            return False

        now = datetime.now().time()

        try:
            start = datetime.strptime(start_time, "%H:%M").time()
            end = datetime.strptime(end_time, "%H:%M").time()

            # 处理跨午夜的情况
            if start <= end:
                return start <= now <= end
            else:
                return now >= start or now <= end
        except ValueError:
            return False

    # ==================== 批量操作 ====================

    def get_users_for_notification(self, user_ids: list, notification_type: str, channel: str = "site") -> list:
        """
        获取应该接收通知的用户列表

        参数:
            user_ids: 用户ID列表
            notification_type: 通知类型
            channel: 通知渠道 (site / email)

        返回:
            list: 应该接收通知的用户ID列表
        """
        result = []

        for user_id in user_ids:
            if channel == "site":
                if self.should_send_site_message(user_id, notification_type):
                    result.append(user_id)
            elif channel == "email":
                if self.should_send_email(user_id, notification_type):
                    result.append(user_id)

        return result

    # ==================== 转换为字典 ====================

    def preference_to_dict(self, preference: NotificationPreference) -> Dict[str, Any]:
        """将偏好对象转换为字典（enabled 由子开关聚合，report/quiet_hours 提供默认值）"""
        site_enabled = bool(
            preference.site_system or preference.site_approval or preference.site_task
        )
        email_enabled = bool(
            preference.email_system or preference.email_approval or preference.email_task
        )
        return {
            "user_id": preference.user_id,
            "site_message": {
                "enabled": site_enabled,
                "system": preference.site_system,
                "approval": preference.site_approval,
                "task": preference.site_task,
                "report": True,
            },
            "email": {
                "enabled": email_enabled,
                "system": preference.email_system,
                "approval": preference.email_approval,
                "task": preference.email_task,
                "report": False,
            },
            "quiet_hours": {
                "enabled": bool(getattr(preference, "quiet_hours_enabled", False)),
                "start": getattr(preference, "quiet_hours_start", None),
                "end": getattr(preference, "quiet_hours_end", None),
            },
            "updated_at": (preference.updated_at.isoformat() if preference.updated_at else None),
        }
