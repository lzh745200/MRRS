"""
消息系统API
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.services.message_service import MessageService
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages-extended", tags=["消息系统"])


class SendMessageRequest(BaseModel):
    """发送消息请求"""

    receiver_id: int
    title: str
    content: str
    message_type: str = "system"
    priority: str = "normal"
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None


@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """发送消息（仅系统/审批/任务类型，不支持任意用户间私信）"""
    # 仅允许发送三种合法类型，防止任意私信绕过权限
    allowed_types = {"system", "approval", "task"}
    if request.message_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"不支持的消息类型: {request.message_type}")

    service = MessageService(db)
    message = service.send_message(
        user_id=request.receiver_id,
        message_type=request.message_type,
        title=request.title,
        content=request.content,
    )
    try:
        write_work_log(db, "message", "send", message.id, f"发送消息: {request.title}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return {"message_id": message.id, "created_at": message.created_at.isoformat()}


@router.get("/unread-count")
async def get_unread_count(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """获取未读消息数量"""
    service = MessageService(db)
    count = service.get_unread_count(user_id=current_user.id)
    return {"unread_count": count}


@router.get("/list")
async def get_messages(
    message_type: Optional[str] = None,
    is_read: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取消息列表"""
    service = MessageService(db)
    # 将 offset/limit 转换为 page/page_size
    page_size = limit
    page = (offset // page_size) + 1
    result = service.get_messages(
        user_id=current_user.id,
        message_type=message_type,
        is_read=is_read,
        page=page,
        page_size=page_size,
    )

    messages = result["items"]
    return {
        "total": result["total"],
        "messages": [
            {
                "id": msg.id,
                "title": msg.title,
                "content": msg.content,
                "message_type": msg.message_type,
                "is_read": msg.is_read,
                "read_at": msg.read_at.isoformat() if msg.read_at else None,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    }


@router.post("/{message_id}/read")
async def mark_as_read(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """标记消息为已读"""
    service = MessageService(db)
    count = service.mark_as_read(user_id=current_user.id, message_ids=[message_id])

    if not count:
        raise HTTPException(status_code=404, detail="消息不存在")

    try:
        write_work_log(db, "message", "mark_read", message_id, "标记消息已读",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)
    return success_response(message="已标记为已读")


@router.post("/read-all")
async def mark_all_as_read(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """标记所有消息为已读"""
    service = MessageService(db)
    count = service.mark_all_as_read(user_id=current_user.id)
    try:
        write_work_log(db, "message", "mark_all_read", 0, "标记全部已读",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)
    return {"marked_count": count}


@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除消息"""
    service = MessageService(db)
    count = service.delete_messages(user_id=current_user.id, message_ids=[message_id])

    if not count:
        raise HTTPException(status_code=404, detail="消息不存在")

    try:
        write_work_log(db, "message", "delete", message_id, "删除消息",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)
    return success_response(message="消息已删除")
