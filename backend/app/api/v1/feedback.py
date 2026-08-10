"""
意见反馈 API - 用于反馈收集机制
使用数据库存储（Feedback 模型）
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.models.issue_tracking import Feedback
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["意见反馈"])

# 反馈类型映射（API type → DB category）
_VALID_TYPES = {"bug", "suggestion", "other"}


class FeedbackCreate(BaseModel):
    type: str = "other"  # bug | suggestion | other
    content: str
    contact: Optional[str] = None


async def _get_user_from_token(authorization: Optional[str] = None) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "").strip()
    try:
        # verify_token (from app.api.v1.auth.auth) performs JWT decoding with
        # blacklist + LRU cache checks via token_manager. It is re-exported from
        # the app.api.v1.auth package __init__. Previously this import failed at
        # runtime because verify_token was not exported, so logged-in users'
        # feedback never recorded their identity (silently caught by except).
        from app.api.v1.auth import verify_token

        info = await verify_token(token, "access_token")
        if info:
            return info.get("username") or str(info.get("id", ""))
    except Exception:
        logger.warning("从 token 获取用户信息失败（反馈将无归属）", exc_info=True)
    return None


@router.get("")
async def list_feedback(
    page: int = 1,
    page_size: int = 20,
    type: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取反馈列表（管理员接口）
    """
    require_admin(current_user, error_message="仅管理员可查看反馈列表")
    query = db.query(Feedback)

    # 按类型筛选
    if type and type != "all":
        query = query.filter(Feedback.category == type)

    # 按时间倒序
    total = query.count()
    offset = (page - 1) * page_size
    rows = query.order_by(Feedback.created_at.desc()).offset(offset).limit(page_size).all()

    items = []
    for row in rows:
        items.append(
            {
                "id": row.id,
                "type": row.category,
                "content": row.content,
                "contact": row.user_email,
                "username": row.user_name,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    return ok_list(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("")
async def submit_feedback(
    body: FeedbackCreate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    提交意见反馈。建议登录后提交（Header: Authorization: Bearer <token>），
    未登录也可提交，但不记录用户标识。
    """
    if not (body.content and body.content.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="反馈内容不能为空")

    category = (body.type or "other").lower()
    if category not in _VALID_TYPES:
        category = "other"

    username = await _get_user_from_token(authorization)

    feedback = Feedback(
        category=category,
        content=body.content.strip(),
        priority="medium",
        status="open",
        user_name=username,
        user_email=(body.contact or "").strip() or None,
        source="web",
    )
    try:
        db.add(feedback)
        safe_commit(db)
        db.refresh(feedback)
    except Exception as e:
        db.rollback()
        logger.error("保存反馈失败: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存反馈失败")

    try:
        write_work_log(
            db, "feedback", "submit", feedback.id, f"提交反馈: {category}",
            user_name=username or "匿名")
    except Exception:
        logger.debug("记录工作日志失败")

    return success_response(message="感谢您的反馈")
