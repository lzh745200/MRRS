"""
Organization Service
组织单位管理服务
"""

import logging
from datetime import timezone, datetime
from typing import List, Optional

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessError
from app.models.organization import Organization
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationStatistics,
    OrganizationTreeNode,
    OrganizationUpdate,
)
from app.services.organization_code_service import OrganizationCodeService
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class OrganizationNotFoundError(BusinessError):
    """组织不存在错误"""

    def __init__(self, org_id: int):
        super().__init__(f"组织不存在: {org_id}")
        self.org_id = org_id


class OrganizationHasSubordinatesError(BusinessError):
    """组织存在下级单位错误"""

    def __init__(self, org_id: int, count: int):
        super().__init__(f"组织存在 {count} 个下级单位，无法删除")
        self.org_id = org_id
        self.subordinate_count = count


class OrganizationCodeDuplicateError(BusinessError):
    """组织编码重复错误"""

    def __init__(self, code: str):
        super().__init__(f"组织编码已存在: {code}")
        self.code = code


class OrganizationInUseError(BusinessError):
    """组织仍被业务数据引用，禁止硬删除（W2-T2 / ADR-0003）"""

    def __init__(self, org_id: int, project_count: int, user_count: int):
        parts = []
        if project_count:
            parts.append(f"{project_count} 个项目")
        if user_count:
            parts.append(f"{user_count} 个用户")
        detail = "、".join(parts) if parts else "业务数据"
        super().__init__(
            f"组织仍被引用（{detail}），无法删除。请先迁移或清理名下数据。"
        )
        self.org_id = org_id
        self.project_count = project_count
        self.user_count = user_count


class OrganizationService:
    """
    组织单位管理服务
    负责组织的创建、查询、更新、删除和层级管理
    """

    def __init__(self, db: Session = None):
        if db is None:
            raise ValueError("OrganizationService requires a valid database session")
        self.db = db
        self.code_service = OrganizationCodeService(db) if db else None

    async def create_organization(self, data: OrganizationCreate, created_by: int) -> Organization:
        """
        创建组织单位

        Args:
            data: 创建数据
            created_by: 创建人ID

        Returns:
            创建的组织对象

        Raises:
            OrganizationNotFoundError: 父组织不存在
            OrganizationCodeDuplicateError: 编码重复
        """
        parent = None
        parent_code = None
        level = 1
        path = "/"

        # 验证父组织
        if data.parent_id:
            parent = self.db.query(Organization).filter(Organization.id == data.parent_id).first()

            if not parent:
                raise OrganizationNotFoundError(data.parent_id)

            parent_code = parent.code
            level = parent.level + 1

        # 生成编码
        prefix = data.code_prefix or "ORG"
        code = self.code_service.generate_code(parent_code=parent_code, prefix=prefix)

        # 排序值自动递增：新增组织默认排到同级末尾
        max_order = (
            self.db.query(func.max(Organization.sort_order))
            .filter(
                Organization.parent_id == data.parent_id
                if data.parent_id
                else Organization.parent_id.is_(None)
            )
            .scalar()
        )
        sort_order = (max_order or 0) + 1

        # 创建组织
        org = Organization(
            code=code,
            name=data.name,
            parent_id=data.parent_id,
            level=level,
            path=path,  # 临时路径，创建后更新
            is_active=data.is_active,
            sort_order=sort_order,
            description=data.description,
            contact_person=data.contact_person,
            contact_phone=data.contact_phone,
            address=data.address,
            created_by=created_by,
        )

        self.db.add(org)
        self.db.flush()  # 获取ID

        # 更新路径
        if parent:
            org.path = f"{parent.path}{org.id}/"
        else:
            org.path = f"/{org.id}/"

        safe_commit(self.db)
        self.db.refresh(org)

        return org

    def get_organization(self, org_id: int) -> Optional[Organization]:
        """
        获取单个组织

        Args:
            org_id: 组织ID

        Returns:
            组织对象或None
        """
        return self.db.query(Organization).filter(Organization.id == org_id).first()

    def get_organization_by_code(self, code: str) -> Optional[Organization]:
        """
        通过编码获取组织

        Args:
            code: 组织编码

        Returns:
            组织对象或None
        """
        return self.db.query(Organization).filter(Organization.code == code).first()

    def get_organization_tree(
        self, root_id: Optional[int] = None, include_inactive: bool = False
    ) -> List[OrganizationTreeNode]:
        """
        获取组织树结构

        Args:
            root_id: 根节点ID，None表示获取所有顶级组织
            include_inactive: 是否包含停用的组织

        Returns:
            组织树节点列表
        """
        query = self.db.query(Organization)

        if not include_inactive:
            query = query.filter(Organization.is_active == True)  # noqa: E712

        if root_id:
            root = self.get_organization(root_id)
            if not root:
                return []

            # 使用路径前缀匹配获取所有子节点
            query = query.filter(Organization.path.like(f"{root.path}%"))
        else:
            # 获取所有顶级组织
            query = query.filter(Organization.parent_id.is_(None))

        organizations = query.order_by(Organization.level, Organization.code).all()

        # 构建树结构
        return self._build_tree(organizations, root_id)

    def _build_tree(self, organizations: List[Organization], parent_id: Optional[int]) -> List[OrganizationTreeNode]:
        """递归构建树结构"""
        tree = []

        for org in organizations:
            if org.parent_id == parent_id:
                children = self._build_tree(organizations, org.id)
                node = OrganizationTreeNode(
                    id=org.id,
                    code=org.code,
                    name=org.name,
                    parent_id=org.parent_id,
                    level=org.level,
                    path=org.path,
                    is_active=org.is_active,
                    description=org.description,
                    contact_person=org.contact_person,
                    contact_phone=org.contact_phone,
                    address=org.address,
                    created_at=org.created_at,
                    created_by=org.created_by,
                    updated_at=org.updated_at,
                    updated_by=org.updated_by,
                    children=children,
                )
                tree.append(node)

        return tree

    def get_subordinate_organizations(
        self, org_id: int, include_self: bool = True, include_inactive: bool = False
    ) -> List[Organization]:
        """
        获取所有下级组织

        Args:
            org_id: 组织ID
            include_self: 是否包含自身
            include_inactive: 是否包含停用的组织

        Returns:
            下级组织列表
        """
        org = self.get_organization(org_id)
        if not org:
            return []

        query = self.db.query(Organization)

        if not include_inactive:
            query = query.filter(Organization.is_active == True)  # noqa: E712

        # 使用路径前缀匹配
        query = query.filter(Organization.path.like(f"{org.path}%"))

        if not include_self:
            query = query.filter(Organization.id != org_id)

        return query.order_by(Organization.level, Organization.code).all()

    def get_subordinate_ids(self, org_id: int, include_self: bool = True) -> List[int]:
        """
        获取所有下级组织ID

        Args:
            org_id: 组织ID
            include_self: 是否包含自身

        Returns:
            下级组织ID列表
        """
        orgs = self.get_subordinate_organizations(org_id, include_self)
        return [org.id for org in orgs]

    def get_ancestors(self, org_id: int) -> List[Organization]:
        """
        获取所有上级组织（从根到父）

        Args:
            org_id: 组织ID

        Returns:
            上级组织列表
        """
        org = self.get_organization(org_id)
        if not org:
            return []

        # 从路径解析祖先ID
        path_ids = [int(id_str) for id_str in org.path.strip("/").split("/") if id_str]

        if not path_ids or path_ids[-1] != org_id:
            return []

        # 排除自身
        ancestor_ids = path_ids[:-1]

        if not ancestor_ids:
            return []

        return self.db.query(Organization).filter(Organization.id.in_(ancestor_ids)).order_by(Organization.level).all()

    async def update_organization(self, org_id: int, data: OrganizationUpdate, updated_by: int) -> Organization:
        """
        更新组织信息

        Args:
            org_id: 组织ID
            data: 更新数据
            updated_by: 更新人ID

        Returns:
            更新后的组织对象

        Raises:
            OrganizationNotFoundError: 组织不存在
        """
        org = self.get_organization(org_id)
        if not org:
            raise OrganizationNotFoundError(org_id)

        # 更新字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(org, field):
                setattr(org, field, value)

        org.updated_by = updated_by
        org.updated_at = datetime.now(timezone.utc)

        safe_commit(self.db)
        self.db.refresh(org)

        return org

    async def delete_organization(self, org_id: int) -> bool:
        """
        删除组织

        Args:
            org_id: 组织ID

        Returns:
            是否删除成功

        Raises:
            OrganizationNotFoundError: 组织不存在
            OrganizationHasSubordinatesError: 存在下级单位
        """
        org = self.get_organization(org_id)
        if not org:
            raise OrganizationNotFoundError(org_id)

        # 检查是否有激活的下级单位（软删除的不阻止删除）
        subordinate_count = self.db.query(Organization).filter(
            Organization.parent_id == org_id,
            Organization.is_active == True  # noqa: E712 -- SQLAlchemy boolean filter
        ).count()

        if subordinate_count > 0:
            raise OrganizationHasSubordinatesError(org_id, subordinate_count)

        # 硬删除前检查名下业务数据（W2-T2 / ADR-0003）：
        # DB 级 ondelete=CASCADE 会让 org 的硬删连带物理删除项目→资金/合同/凭证，
        # 必须在应用层拒绝并列出引用计数，要求先迁移。
        from app.models.project import Project
        from app.models.user import User

        project_count = self.db.query(Project).filter(
            Project.organization_id == org_id,
            Project.is_active == True  # noqa: E712 -- SQLAlchemy boolean filter
        ).count()
        user_count = self.db.query(User).filter(
            User.organization_id == org_id,
            User.is_active == True  # noqa: E712
        ).count()
        if project_count or user_count:
            raise OrganizationInUseError(org_id, project_count, user_count)

        self.db.delete(org)
        safe_commit(self.db)

        return True

    def get_statistics(self, root_id: Optional[int] = None) -> OrganizationStatistics:
        """
        获取组织统计信息

        Args:
            root_id: 根组织ID，None表示全部

        Returns:
            统计信息
        """
        query = self.db.query(Organization)

        if root_id:
            org = self.get_organization(root_id)
            if org:
                query = query.filter(Organization.path.like(f"{org.path}%"))

        organizations = query.all()

        total = len(organizations)
        active = sum(1 for o in organizations if o.is_active)
        inactive = total - active

        # 按层级统计
        by_level = {}
        max_level = 0
        for org in organizations:
            level_key = str(org.level)
            by_level[level_key] = by_level.get(level_key, 0) + 1
            max_level = max(max_level, org.level)

        return OrganizationStatistics(
            total=total,
            active=active,
            inactive=inactive,
            by_level=by_level,
            max_level=max_level,
        )

    def search_organizations(self, keyword: str, limit: int = 20, include_inactive: bool = False) -> List[Organization]:
        """
        搜索组织

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            include_inactive: 是否包含停用的组织

        Returns:
            匹配的组织列表
        """
        query = self.db.query(Organization)

        if not include_inactive:
            query = query.filter(Organization.is_active == True)  # noqa: E712

        # 搜索名称和编码
        query = query.filter(
            or_(
                Organization.name.ilike(f"%{keyword}%"),
                Organization.code.ilike(f"%{keyword}%"),
            )
        )

        return query.limit(limit).all()

    def validate_parent_child_relationship(self, parent_id: int, child_id: int) -> bool:
        """
        验证父子关系是否有效（防止循环引用）

        Args:
            parent_id: 父组织ID
            child_id: 子组织ID

        Returns:
            关系是否有效
        """
        if parent_id == child_id:
            return False

        # 检查parent是否是child的后代
        child = self.get_organization(child_id)
        if not child:
            return False

        subordinates = self.get_subordinate_ids(child_id, include_self=False)
        return parent_id not in subordinates

    def batch_update_sort_orders(self, sort_list: List[dict]) -> tuple[bool, int]:
        """批量更新组织排序

        Args:
            sort_list: 排序列表，格式：[{"id": 1, "sort_order": 1}, ...]

        Returns:
            tuple[bool, int]: (是否成功, 更新数量)
        """
        try:
            updated_count = 0

            for item in sort_list:
                org_id = item.get("id")
                sort_order = item.get("sort_order")

                if org_id is None or sort_order is None:
                    continue

                # 更新排序
                org = self.db.query(Organization).filter(Organization.id == org_id).first()

                if org:
                    org.sort_order = sort_order
                    updated_count += 1

            safe_commit(self.db)
            return True, updated_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"批量更新组织排序失败: {e}")
            return False, 0
