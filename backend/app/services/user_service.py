"""
用户服务

提供用户 CRUD、认证、查询等功能。
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from app.core.transaction import safe_commit
from app.core.constants import ALL_ROLES

logger = logging.getLogger(__name__)

# 校验用完整角色集合（含兼容的历史角色值）
VALID_ROLES = list(ALL_ROLES)

# 数据范围四值（与 app/api/v1/auth/users.py 的 VALID_SCOPES 同口径）。
# 账号开通包导入时必须重新校验，不信任包内声明（见 deliverables/账号开通包实施方案.md §十六-5/6）。
VALID_DATA_SCOPES = ("all", "org", "org_children", "self")

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


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
            # 2026-10-29 审计：原先不落 phone（schema 还叫 phone_number），
            # 注册链路传的电话被静默丢弃。phone 是 PII 加密列（ADR-0005），
            # 必须经模型写入而非裸 SQL。兼容旧的 phone_number 键名。
            phone=data.get("phone") or data.get("phone_number"),
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

    def create_user_with_password_hash(
        self,
        username: str,
        password_hash: str,
        *,
        role: str = "user",
        organization_id: Optional[int] = None,
        data_scope: str = "org",
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        must_change_password: bool = True,
        credential_expires_at=None,
        commit: bool = True,
    ):
        """用**已哈希**的初始口令建号（账号开通包专用，2026-11-17）。

        账号开通包只携带「包专用初始密码」的 bcrypt 哈希，明文由源机管理员另渠道
        交付给用户（见 deliverables/账号开通包实施方案.md §三/§十六-1）。因此导入
        链路不能走 ``create_user``——它只接受明文再哈希，会让调用方要么在内存里
        持有明文，要么绕不过去。

        安全约束：
        - 只接受 bcrypt 哈希（``$2a$/$2b$/$2y$``），看起来像明文一律拒绝，
          防止调用方误把明文传进来落库；
        - ``role`` / ``data_scope`` 在本地重新归一与校验，不信任包内声明；
        - ``must_change_password`` 默认 True，由导入端强制，包内同名字段不生效；
        - ``commit=False`` 时只 flush，供导入链路把整包放进同一事务。
        """
        from app.core.constants import normalize_role
        from app.models.user import User

        if self.db is None:
            return None

        if not isinstance(password_hash, str) or not password_hash.startswith(_BCRYPT_PREFIXES):
            raise ValueError("password_hash 必须是 bcrypt 哈希，禁止直接传入明文口令")

        normalized_role = normalize_role(role)
        if normalized_role not in VALID_ROLES:
            raise ValueError(f"无效的角色: {role}")
        if data_scope not in VALID_DATA_SCOPES:
            raise ValueError(f"无效的数据范围: {data_scope}")
        if not username or not str(username).strip():
            raise ValueError("用户名不能为空")

        if self.db.query(User).filter(User.username == username).first() is not None:
            raise ValueError(f"用户名已存在: {username}")

        user = User(
            username=username,
            email=email,
            hashed_password=password_hash,
            full_name=full_name,
            phone=phone,
            role=normalized_role,
            organization_id=organization_id,
            data_scope=data_scope,
            is_active=True,
            must_change_password=bool(must_change_password),
            credential_expires_at=credential_expires_at,
        )
        self.db.add(user)
        if commit:
            safe_commit(self.db)
            self.db.refresh(user)
        else:
            self.db.flush()
        return user

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


def expire_provisioned_credentials(db: Session) -> int:
    """P3：停用已过期且仍处于首登改密状态的账号（幂等）。

    只处理 ``credential_expires_at < now`` 且 ``must_change_password=True`` 的账号，
    避免误伤正常长期账号；禁用同时递增 token_version 让既有会话立即失效。
    """
    from app.utils.audit_logger import AuditLogger
    from app.utils.time_utils import utcnow

    if db is None:
        return 0
    from app.models.user import User

    now = utcnow()
    rows = (
        db.query(User)
        .filter(
            User.credential_expires_at.isnot(None),
            User.credential_expires_at < now,
            User.must_change_password.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )
    for user in rows:
        user.is_active = False
        user.token_version = int(user.token_version or 0) + 1
        AuditLogger.log_safely(
            action="account_credential_expired",
            user_id=user.id,
            username=user.username,
            resource_type="user",
            resource_id=user.id,
            details={"reason": "credential_expires_at"},
        )
    if rows:
        safe_commit(db)
    return len(rows)
