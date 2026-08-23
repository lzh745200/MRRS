"""
待办事项API

提供待办事项的增删改查端点。
"""

import logging
from datetime import timezone, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.todo import Todo
from app.core.response import success_response
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/todos", tags=["待办事项"])


# ==================== 请求 / 响应模型 ====================


class TodoCreate(BaseModel):
    """创建待办请求"""

    title: str = Field(..., min_length=1, max_length=500, description="待办标题")
    description: Optional[str] = Field(None, description="待办描述")
    deadline: Optional[str] = Field(None, description="截止日期")
    priority: str = Field("medium", description="优先级: high/medium/low")


class TodoUpdate(BaseModel):
    """更新待办请求"""

    title: Optional[str] = Field(None, min_length=1, max_length=500, description="待办标题")
    description: Optional[str] = Field(None, description="待办描述")
    deadline: Optional[str] = Field(None, description="截止日期")
    completed: Optional[bool] = Field(None, description="是否完成")
    priority: Optional[str] = Field(None, description="优先级: high/medium/low")


class TodoResponse(BaseModel):
    """待办响应"""

    id: int
    title: str
    description: Optional[str] = None
    deadline: Optional[str] = None
    completed: bool
    priority: str
    user_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TodoListResponse(BaseModel):
    """待办列表响应"""

    items: List[TodoResponse]
    total: int


# ==================== 接口 ====================


@router.get("/{todo_id}", response_model=TodoResponse, summary="获取待办详情")
async def get_todo(
    todo_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个待办事项详情"""
    todo = (
        db.query(Todo)
        .filter(
            Todo.id == todo_id,
            Todo.user_id == current_user.id,
        )
        .first()
    )

    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="待办事项不存在")

    return TodoResponse(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        deadline=todo.deadline,
        completed=todo.completed,
        priority=todo.priority,
        user_id=todo.user_id,
        created_at=todo.created_at.isoformat() if todo.created_at else None,
        updated_at=todo.updated_at.isoformat() if todo.updated_at else None,
    )


@router.get("", response_model=TodoListResponse, summary="获取待办列表")
async def get_todos(
    completed: Optional[bool] = Query(None, description="是否完成"),
    priority: Optional[str] = Query(None, description="优先级过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的待办事项列表"""
    try:
        query = db.query(Todo).filter(Todo.user_id == current_user.id)

        if completed is not None:
            query = query.filter(Todo.completed == completed)
        if priority:
            query = query.filter(Todo.priority == priority)

        total = query.count()
        items = (
            query.order_by(Todo.completed.asc(), Todo.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return TodoListResponse(
            items=[
                TodoResponse(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    deadline=item.deadline,
                    completed=item.completed,
                    priority=item.priority,
                    user_id=item.user_id,
                    created_at=item.created_at.isoformat() if item.created_at else None,
                    updated_at=item.updated_at.isoformat() if item.updated_at else None,
                )
                for item in items
            ],
            total=total,
        )
    except Exception as e:
        logger.error(f"获取待办列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取待办列表失败，请稍后重试或联系管理员",
        )


@router.post("", response_model=TodoResponse, summary="创建待办事项")
async def create_todo(
    data: TodoCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新的待办事项"""
    try:
        todo = Todo(
            title=data.title,
            description=data.description,
            deadline=data.deadline,
            priority=data.priority,
            completed=False,
            user_id=current_user.id,
        )
        db.add(todo)
        safe_commit(db)
        db.refresh(todo)

        try:
            write_work_log(
                db, "todo", "create", todo.id, f"创建待办: {todo.title}",
                user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:
            logger.debug("记录工作日志失败")

        return TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            deadline=todo.deadline,
            completed=todo.completed,
            priority=todo.priority,
            user_id=todo.user_id,
            created_at=todo.created_at.isoformat() if todo.created_at else None,
            updated_at=todo.updated_at.isoformat() if todo.updated_at else None,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"创建待办失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建待办失败，请稍后重试或联系管理员",
        )


@router.put("/{todo_id}", response_model=TodoResponse, summary="更新待办事项")
async def update_todo(
    todo_id: int,
    data: TodoUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新待办事项"""
    try:
        todo = (
            db.query(Todo)
            .filter(
                Todo.id == todo_id,
                Todo.user_id == current_user.id,
            )
            .first()
        )

        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="待办事项不存在")

        # 只更新提供了的字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(todo, field, value)

        todo.updated_at = datetime.now(timezone.utc)
        safe_commit(db)
        db.refresh(todo)

        try:
            write_work_log(
                db, "todo", "update", todo.id, f"更新待办: {todo.title}",
                user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:
            logger.debug("记录工作日志失败")

        return TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            deadline=todo.deadline,
            completed=todo.completed,
            priority=todo.priority,
            user_id=todo.user_id,
            created_at=todo.created_at.isoformat() if todo.created_at else None,
            updated_at=todo.updated_at.isoformat() if todo.updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新待办失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新待办失败，请稍后重试或联系管理员",
        )


@router.delete("/{todo_id}", summary="删除待办事项")
async def delete_todo(
    todo_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除待办事项"""
    try:
        todo = (
            db.query(Todo)
            .filter(
                Todo.id == todo_id,
                Todo.user_id == current_user.id,
            )
            .first()
        )

        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="待办事项不存在")

        db.delete(todo)
        safe_commit(db)

        try:
            write_work_log(
                db, "todo", "delete", todo_id, f"删除待办: {todo.title}",
                user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:
            logger.debug("记录工作日志失败")

        return success_response(data={"id": todo_id}, message="待办事项已删除")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除待办失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除待办失败，请稍后重试或联系管理员",
        )


@router.patch("/{todo_id}/toggle", response_model=TodoResponse, summary="切换完成状态")
async def toggle_todo(
    todo_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """切换待办事项的完成状态"""
    try:
        todo = (
            db.query(Todo)
            .filter(
                Todo.id == todo_id,
                Todo.user_id == current_user.id,
            )
            .first()
        )

        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="待办事项不存在")

        todo.completed = not todo.completed
        todo.updated_at = datetime.now(timezone.utc)
        safe_commit(db)
        db.refresh(todo)

        return TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            deadline=todo.deadline,
            completed=todo.completed,
            priority=todo.priority,
            user_id=todo.user_id,
            created_at=todo.created_at.isoformat() if todo.created_at else None,
            updated_at=todo.updated_at.isoformat() if todo.updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"切换待办状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换待办状态失败，请稍后重试或联系管理员",
        )
