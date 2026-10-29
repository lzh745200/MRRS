"""用户 Pydantic Schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """用户基础模型"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[str] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, min_length=1, max_length=100, description="姓名")
    # 2026-10-29 审计：原字段名 phone_number，而 users 表列名是 phone，且
    # create_user 只取 username/email/full_name/role —— 注册链路传的电话被**静默丢弃**
    # （前端也不传，所以才一直没被发现）。统一为 phone 并让 service 落库。
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    is_active: Optional[bool] = Field(default=True, description="是否激活")
    is_superuser: Optional[bool] = Field(default=False, description="是否超级管理员")
    # role_id 已删除：users 表无 role_id 列（角色由 role 字符串承载），保留只会让调用方
    # 以为"按角色 ID 授权"生效，实际被静默忽略。


class UserCreate(UserBase):
    """创建用户"""

    password: str = Field(..., min_length=12, description="密码，至少12位")


class UserUpdate(BaseModel):
    """更新用户"""

    email: Optional[str] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    role_id: Optional[int] = None
    password: Optional[str] = Field(None, min_length=12)


class UserInDB(UserBase):
    """数据库中的用户"""

    id: int
    hashed_password: str
    created_at: datetime
    updated_at: datetime


class UserResponse(UserBase):
    """用户响应"""

    id: int
    created_at: datetime
    updated_at: datetime
