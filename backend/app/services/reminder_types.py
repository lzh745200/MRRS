"""提醒类消息类型（单一事实源）。

提醒中心列表过滤（`reminder_orchestrator`）与处置归属校验
（`reminder_disposition_service`）必须使用同一集合：任何一个列表能看到的提醒，
都必须能被处置；反之不在清单内的消息不允许在此入口处置。
"""

REMINDER_MESSAGE_TYPES = (
    "approval_overtime",
    "approval_approaching",
    "deadline_warning",
    "budget_warning",
    "backup_reminder",
    "package_reminder",
)


def is_reminder_type(message_type: str) -> bool:
    """是否属于提醒中心管理的消息类型。"""
    return message_type in REMINDER_MESSAGE_TYPES
