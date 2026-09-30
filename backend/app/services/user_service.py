"""
用户服务

提供用户 CRUD、认证、查询等功能。
"""

import logging
from typing import List

from sqlalchemy.orm import Session
from app.core.transaction import safe_commit
from app.core.constants import ALL_ROLES

logger = logging.getLogger(__name__)

# 校验用完整角色集合（含兼容的历史角色值）
VALID_ROLES = list(ALL_ROLES)


class UserService:
    """用户服务"""

    def __init__(self, db: Session = None):
        self.db = db

    def get_user_by_username(self, username: str):
        """通过用户名获取用户"""
        if self.db is None:
            return None
        from app.models.user import User

        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_id(self, user_id: int):
        """通过 ID 获取用户"""
        if self.db is None:
            return None
        from app.models.user import User

        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: str):
        """通过邮箱获取用户"""
        if self.db is None:
            return None
        from app.models.user import User

        return self.db.query(User).filter(User.email == email).first()

    def get_users(
        self,
        skip: int = 0,
        limit: int = 50,
        role: str = None,
        is_active: bool = None,
        search: str = None,
    ) -> List:
        """获取用户列表"""
        if self.db is None:
            return []
        from app.models.user import User

        query = self.db.query(User)
        if role:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if search:
            query = query.filter(
                (User.username.contains(search))
                | (User.full_name.contains(search))
                | (User.email.contains(search))
            )
        return query.offset(skip).limit(limit).all()

    def create_user(self, data: dict):
        """创建用户"""
        if self.db is None:
            return None
        from app.models.user import User
        from app.core.security import get_password_hash
        from app.core.constants import normalize_role

        user = User(
            username=data["username"],
            email=data.get("email"),
            hashed_password=get_password_hash(data["password"]),
            full_name=data.get("full_name"),
            role=normalize_role(data.get("role", "user")),
            is_active=True,
        )
        self.db.add(user)
        safe_commit(self.db)
        self.db.refresh(user)
        return user

    # 允许经本服务更新的字段白名单（纵深防御）。
    # 历史实现是无过滤 setattr：任何调用方传入 role / is_superuser /
    # hashed_password / is_active 都能一步提权或篡改凭据（深审 LIVE）。
    UPDATABLE_FIELDS = frozenset({
        "email",
        "full_name",
        "phone",
        "department",
        "position",
        "organization_id",
        "data_scope",
        "allowed_menus",
        "avatar",
        "remarks",
    })

    def update_user(self, user_id: int, data: dict):
        """更新用户（仅白名单字段；角色/凭据/启用状态必须走专用端点）"""
        user = self.get_user_by_id(user_id)
        if user is None:
            return None
        for key, value in data.items():
            if key not in self.UPDATABLE_FIELDS:
                logger.warning("update_user: 忽略非白名单字段 '%s'（user_id=%s）", key, user_id)
                continue
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        if self.db:
            safe_commit(self.db)
            self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        user = self.get_user_by_id(user_id)
        if user is None:
            return False
        if self.db:
            self.db.delete(user)
            safe_commit(self.db)
        return True

    @staticmethod
    async def get_user(user_id: int):
        """异步获取用户（兼容旧接口）"""
        return None
