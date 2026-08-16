"""权限包模型

权限包 = 菜单套餐：管理员预定义一组可见菜单 key，批量绑定给普通用户(user/viewer)。
菜单解析优先级（见 app.api.v1.menus._get_user_accessible_menu_keys）：
    用户级 allowed_menus 配置 > 绑定的启用中权限包 > 角色默认菜单
"""

import json

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class PermissionPack(Base):
    """权限包表"""

    __tablename__ = "permission_packs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, comment="权限包名称")
    description = Column(Text, comment="权限包描述")
    menu_keys = Column(Text, default="[]", comment="菜单key列表(JSON数组)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人用户ID",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    @property
    def menu_keys_list(self) -> list:
        """菜单key列表（从JSON解析，非法JSON时返回空列表）"""
        if not self.menu_keys:
            return []
        try:
            return json.loads(self.menu_keys)
        except (json.JSONDecodeError, TypeError):
            return []

    def __repr__(self):
        return f"<PermissionPack(id={self.id}, name='{self.name}', is_active={self.is_active})>"
