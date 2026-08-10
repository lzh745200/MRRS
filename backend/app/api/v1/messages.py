"""
消息通知API

任务 7.9: 实现消息通知API端点
- 消息列表
- 未读数量
- 标记已读
- 批量删除
- 通知偏好管理
- 模板管理

需求: 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 7.1
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import get_current_user
from app.services.message_service import MessageService
from app.services.message_template_service import MessageTemplateService
from app.services.notification_preference_service import NotificationPreferenceService
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["消息通知"])


# ==================== 请求 / 响应模型 ====================


class MessageResponse(BaseModel):
    """消息响应"""

    id: int
    message_type: str
    title: str
    content: str
    link: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    """消息列表响应"""

    items: List[MessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UnreadCountResponse(BaseModel):
    """未读数量响应"""

    total: int
    by_type: dict


class MarkReadRequest(BaseModel):
    """标记已读请求"""

    message_ids: List[int] = Field(..., min_length=1)


class DeleteMessagesRequest(BaseModel):
    """删除消息请求"""

    message_ids: List[int] = Field(..., min_length=1)


class NotificationPreferenceResponse(BaseModel):
    """通知偏好响应"""

    user_id: int
    site_message: dict
    email: dict
    quiet_hours: dict
    updated_at: Optional[str] = None


class UpdateSiteMessageSettingsRequest(BaseModel):
    """更新站内消息设置请求"""

    enabled: bool = True
    system: bool = True
    approval: bool = True
    task: bool = True
    report: bool = True


class UpdateEmailSettingsRequest(BaseModel):
    """更新邮件设置请求"""

    enabled: bool = True
    system: bool = True
    approval: bool = True
    task: bool = True
    report: bool = False


class UpdateQuietHoursRequest(BaseModel):
    """更新免打扰时段请求"""

    enabled: bool
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class UpdateNotificationPreferencesRequest(BaseModel):
    """统一更新通知偏好请求（前端扁平结构）"""

    email_approval: Optional[bool] = None
    email_task: Optional[bool] = None
    email_system: Optional[bool] = None
    site_approval: Optional[bool] = None
    site_task: Optional[bool] = None
    site_system: Optional[bool] = None


# ==================== 依赖注入 ====================


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    return MessageService(db)


def get_preference_service(
    db: Session = Depends(get_db),
) -> NotificationPreferenceService:
    return NotificationPreferenceService(db)


def get_template_service(db: Session = Depends(get_db)) -> MessageTemplateService:
    return MessageTemplateService(db)


# ==================== 辅助函数 ====================


def _parse_query_date(val: Optional[str]) -> Optional[datetime]:
    """将查询参数中的日期字符串安全转换为 datetime"""
    if not val or not val.strip():
        return None
    val = val.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


# ==================== 消息接口 ====================


@router.get("", response_model=MessageListResponse)
async def get_messages(
    message_type: Optional[str] = Query(None, description="消息类型: system / approval / task"),
    is_read: Optional[bool] = Query(None, description="是否已读"),
    start_date: Optional[str] = Query(None, description="开始时间 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束时间 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """
    获取消息列表

    需求: 5.3 - 提供消息列表页面，支持按类型和时间筛选
    """
    result = service.get_messages(
        user_id=current_user.id,
        message_type=message_type,
        is_read=is_read,
        start_date=_parse_query_date(start_date),
        end_date=_parse_query_date(end_date),
        page=page,
        page_size=page_size,
    )

    return MessageListResponse(
        items=[MessageResponse.model_validate(m) for m in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """
    获取未读消息数量

    需求: 5.2 - 显示未读消息数量
    """
    total = service.get_unread_count(current_user.id)
    by_type = service.get_unread_count_by_type(current_user.id)

    return UnreadCountResponse(total=total, by_type=by_type)


@router.post("/mark-read")
async def mark_messages_as_read(
    data: MarkReadRequest,
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """
    批量标记消息为已读

    需求: 5.4, 5.5 - 标记消息为已读，支持批量操作
    """
    count = service.mark_as_read(current_user.id, data.message_ids)
    try:
        write_work_log(service.db, "message", "mark_read", 0, f"标记{count}条消息已读",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    return {"message": f"已标记 {count} 条消息为已读", "count": count}


@router.post("/mark-all-read")
async def mark_all_as_read(
    message_type: Optional[str] = Query(None, description="消息类型，不指定则标记所有"),
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """标记所有消息为已读"""
    count = service.mark_all_as_read(current_user.id, message_type)
    try:
        write_work_log(service.db, "message", "mark_all_read", 0, "标记全部已读",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    return {"message": f"已标记 {count} 条消息为已读", "count": count}


@router.delete("")
async def delete_messages(
    data: DeleteMessagesRequest,
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """
    批量删除消息

    需求: 5.5 - 支持批量删除
    """
    count = service.delete_messages(current_user.id, data.message_ids)
    try:
        write_work_log(service.db, "message", "delete", 0, f"删除{count}条消息",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    return {"message": f"已删除 {count} 条消息", "count": count}


@router.delete("/read")
async def delete_all_read_messages(
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """删除所有已读消息"""
    count = service.delete_all_read_messages(current_user.id)
    try:
        write_work_log(service.db, "message", "delete_read", 0, f"删除{count}条已读消息",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    return {"message": f"已删除 {count} 条已读消息", "count": count}


@router.get("/stats/summary")
async def get_message_stats(
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """获取消息统计信息"""
    return service.get_message_stats(current_user.id)


# ==================== 近期动态接口（单机版） ====================


@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = Query(10, ge=1, le=50, description="返回条数"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取近期系统动态

    从审计日志中提取最近的系统操作记录，适配单机版使用场景。
    不依赖外部消息队列或WebSocket，直接从本地数据库查询。
    """
    from app.models.audit import AuditLog

    # 只查询有意义的操作（排除 read/api_call 等高频低价值操作）
    meaningful_actions = [
        "create",
        "update",
        "delete",
        "import",
        "export",
        "login",
        "backup",
    ]

    try:
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.action.in_(meaningful_actions))
            .filter(AuditLog.status == "success")
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

        # 将审计日志转为前端需要的活动格式
        action_title_map = {
            "create": "新增记录",
            "update": "更新数据",
            "delete": "删除记录",
            "import": "数据导入",
            "export": "数据导出",
            "login": "用户登录",
            "backup": "数据备份",
        }
        action_type_map = {
            "create": "success",
            "update": "info",
            "delete": "warning",
            "import": "success",
            "export": "info",
            "login": "info",
            "backup": "success",
        }
        resource_name_map = {
            "project": "帮扶项目",
            "village": "帮扶村",
            "supported_village": "帮扶村",
            "fund": "资金",
            "todo": "待办事项",
            "user": "用户",
            "policy": "政策",
            "school": "学校",
            "report": "报表",
        }

        items = []
        for log in logs:
            action = log.action or "update"
            resource = log.resource_type or ""
            resource_cn = resource_name_map.get(resource, resource)
            title = action_title_map.get(action, "系统操作")
            if resource_cn:
                title = f"{resource_cn}{title}"

            username = log.username or "系统"
            description = f"用户 {username} 执行了{title}操作"
            if log.resource_id:
                description += f"（ID: {log.resource_id}）"

            created_at = log.created_at
            if created_at:
                time_str = created_at.strftime("%Y-%m-%d %H:%M")
            else:
                time_str = ""

            items.append(
                {
                    "id": str(log.id),
                    "title": title,
                    "description": description,
                    "time": time_str,
                    "type": action_type_map.get(action, "info"),
                }
            )

        return ok_list(items, len(items))

    except OperationalError as e:
        logger.warning("获取近期动态失败 (DB operational): %s", e)
        return ok_list([], 0)
    except ProgrammingError as e:
        logger.warning("获取近期动态失败 (schema): %s", e)
        return ok_list([], 0)
    except Exception as e:
        logger.error("获取近期动态时发生未预期错误: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取近期动态失败: {type(e).__name__}")


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_user=Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
):
    """获取单条消息详情"""
    message = service.get_message(message_id, current_user.id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")

    # 自动标记为已读
    if not message.is_read:
        service.mark_single_as_read(current_user.id, message_id)
        message.is_read = True

    return MessageResponse.model_validate(message)


# ==================== 通知偏好接口 ====================

notifications_router = APIRouter(prefix="/notifications", tags=["通知设置"])


@notifications_router.get("/preferences")
async def get_notification_preferences(
    current_user=Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_preference_service),
):
    """
    获取通知偏好设置

    需求: 6.2 - 用户可配置接收哪些类型的通知
    返回嵌套结构 + 前端扁平字段，确保两端对齐
    """
    preference = service.get_preference(current_user.id)
    result = service.preference_to_dict(preference)

    site = result.get("site_message", {})
    email = result.get("email", {})
    result["site_system"] = site.get("system", True)
    result["site_approval"] = site.get("approval", True)
    result["site_task"] = site.get("task", True)
    result["email_system"] = email.get("system", True)
    result["email_approval"] = email.get("approval", True)
    result["email_task"] = email.get("task", True)

    return result


@notifications_router.put("/preferences")
async def update_notification_preferences(
    data: UpdateNotificationPreferencesRequest,
    current_user=Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_preference_service),
):
    """统一更新通知偏好（前端扁平结构）"""
    preference = service.get_preference(current_user.id)
    pref_dict = service.preference_to_dict(preference)

    site = pref_dict.get("site_message", {})
    email = pref_dict.get("email", {})

    if data.site_system is not None:
        site["system"] = data.site_system
    if data.site_approval is not None:
        site["approval"] = data.site_approval
    if data.site_task is not None:
        site["task"] = data.site_task

    if data.email_system is not None:
        email["system"] = data.email_system
    if data.email_approval is not None:
        email["approval"] = data.email_approval
    if data.email_task is not None:
        email["task"] = data.email_task

    service.update_site_message_settings(
        user_id=current_user.id,
        enabled=site.get("enabled", True),
        system=site.get("system", True),
        approval=site.get("approval", True),
        task=site.get("task", True),
        report=site.get("report", True),
    )
    service.update_email_settings(
        user_id=current_user.id,
        enabled=email.get("enabled", True),
        system=email.get("system", True),
        approval=email.get("approval", True),
        task=email.get("task", True),
        report=email.get("report", False),
    )

    updated = service.get_preference(current_user.id)
    return service.preference_to_dict(updated)


@notifications_router.put("/preferences/site-message")
async def update_site_message_settings(
    data: UpdateSiteMessageSettingsRequest,
    current_user=Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_preference_service),
):
    """更新站内消息设置"""
    preference = service.update_site_message_settings(
        user_id=current_user.id,
        enabled=data.enabled,
        system=data.system,
        approval=data.approval,
        task=data.task,
        report=data.report,
    )
    return service.preference_to_dict(preference)


@notifications_router.put("/preferences/email")
async def update_email_settings(
    data: UpdateEmailSettingsRequest,
    current_user=Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_preference_service),
):
    """更新邮件通知设置"""
    preference = service.update_email_settings(
        user_id=current_user.id,
        enabled=data.enabled,
        system=data.system,
        approval=data.approval,
        task=data.task,
        report=data.report,
    )
    return service.preference_to_dict(preference)


@notifications_router.put("/preferences/quiet-hours")
async def update_quiet_hours(
    data: UpdateQuietHoursRequest,
    current_user=Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_preference_service),
):
    """更新免打扰时段设置"""
    preference = service.update_quiet_hours(
        user_id=current_user.id,
        enabled=data.enabled,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    return service.preference_to_dict(preference)
