"""权限包模型

权限包 = 菜单套餐：管理员预定义一组可见菜单 key，批量绑定给普通用户(user/viewer)。
菜单解析优先级（见 app.api.v1.menus._get_user_accessible_menu_keys）：
    用户级 allowed_menus 配置 > 绑定的启用中权限包 > 角色默认菜单

R33 起新增 `grants`（模块授权矩阵）：权限包从"只有可见性"升级为"可见性 + 可写性"，
`menu_keys` 保留用于向后兼容与回滚 —— `grants` 为空时由 `menu_keys` 派生（一律按 edit）。
"""

import json

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base, UtcDateTime


class PermissionPack(Base):
    """权限包表"""

    __tablename__ = "permission_packs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, comment="权限包名称")
    description = Column(Text, comment="权限包描述")
    menu_keys = Column(Text, default="[]", comment="菜单key列表(JSON数组)")
    grants = Column(
        Text,
        nullable=True,
        comment="模块授权矩阵(JSON对象: module_key -> edit/view/none)；空则由 menu_keys 派生",
    )
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人用户ID",
    )
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="创建时间")
    updated_at = Column(UtcDateTime(), onupdate=func.now(), comment="更新时间")

    @property
    def menu_keys_list(self) -> list:
        """菜单key列表（从JSON解析，非法JSON时返回空列表）"""
        if not self.menu_keys:
            return []
        try:
            return json.loads(self.menu_keys)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def grants_dict(self) -> dict:
        """模块授权矩阵；`grants` 为空或非法时由 `menu_keys` 派生（一律 edit）。

        派生规则是为了向后兼容：老包只有 `menu_keys`，其菜单按"可写"生效 ——
        与升级前"可见即可写"的语义完全一致，升级不改变存量行为。
        """
        if self.grants:
            try:
                data = json.loads(self.grants)
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                return {
                    str(k): str(v)
                    for k, v in data.items()
                    if isinstance(v, str) and v in ("edit", "view", "none")
                }
        return {str(k): "edit" for k in self.menu_keys_list if isinstance(k, str)}

    def __repr__(self):
        return f"<PermissionPack(id={self.id}, name='{self.name}', is_active={self.is_active})>"
