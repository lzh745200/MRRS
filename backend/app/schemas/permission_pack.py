"""权限包 Schemas

权限包 = 菜单套餐：name + menu_keys(JSON数组) + 绑定用户。
注意：menu_keys 的合法性校验（必须是 menus.MENU_DEFINITIONS 中存在的 key）放在路由层
—— schema 层 import menus 会有循环依赖风险。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PackCreate(BaseModel):
    """创建权限包"""

    name: str = Field(..., min_length=1, max_length=100, description="权限包名称（唯一）")
    description: Optional[str] = Field(None, description="权限包描述")
    menu_keys: list[str] = Field(default_factory=list, description="菜单key列表")
    is_active: bool = Field(True, description="是否启用")


class PackUpdate(BaseModel):
    """更新权限包（仅更新传入字段）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="权限包名称（唯一）")
    description: Optional[str] = Field(None, description="权限包描述")
    menu_keys: Optional[list[str]] = Field(None, description="菜单key列表")
    is_active: Optional[bool] = Field(None, description="是否启用")


class PackResponse(BaseModel):
    """权限包响应"""

    id: int
    name: str
    description: Optional[str] = None
    menu_keys: list[str] = []
    is_active: bool = True
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    bound_user_count: int = 0


class BindUsersRequest(BaseModel):
    """批量绑定/解绑用户"""

    user_ids: list[int] = Field(default_factory=list, description="目标用户ID列表")
