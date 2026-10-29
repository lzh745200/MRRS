"""
Organization Service
组织单位管理服务
"""

import logging
from datetime import timezone, datetime
from typing import Any, Dict, List, Optional

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
            level = self.code_service.level_order(parent.level) or 0

        # 编码即行政区划代码（2026-10-27 P1 修复）：
        # 此前这里调用 generate_code() 生成随机 `ORG-XXXXXXXX`，把调用方传入的
        # 6 位行政区划代码**整个丢弃** —— 系统初始化（system/init.py）正是走这条路径，
        # 于是首启建出的根组织编码成了随机串（实测传 522700 落库 ORG-848B7F7C、level=1），
        # 与「编码 = 行政区划代码、跨机匹配唯一依据」的契约直接冲突。
        # 现在以传入编码为准：格式 → 权威表（存在性/别名）→ 父子一致 → 层级推导。
        code = self.code_service.normalize_admin_code(getattr(data, "code", None) or "")
        code = self.code_service.validate_admin_code(code, parent_code)

        inferred_level = self.code_service.infer_level(code)
        level = self.code_service.level_order(inferred_level) or 0
        if not level:
            raise ValueError("组织编码无法判定层级，请核对 6 位行政区划代码")

        # 跨级校验：根组织可为任一层级（省/市州/县市），下级必须恰为父级 +1
        if parent is not None:
            parent_level = self.code_service.level_order(parent.level) or 0
            if level != parent_level + 1:
                raise ValueError(
                    "层级必须逐级挂接：省级 → 市州级 → 县市级（当前上级层级不匹配）"
                )

        # 编码唯一性：跨机匹配依赖它，重复即拒绝
        if self.db.query(Organization).filter(Organization.code == code).first():
            raise OrganizationCodeDuplicateError(code)

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
            level=str(level),  # 与端点同口径：落库保持历史"深度数字"字符串
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

        # 更新路径（父级 path 可能为 NULL —— 直接拼接会得到 "None123/"，
        # 污染下级 path 并让祖先解析失败，故回退到父 ID 单段路径）
        if parent:
            parent_path = parent.path or f"/{parent.id}/"
            org.path = f"{parent_path}{org.id}/"
        else:
            org.path = f"/{org.id}/"

        safe_commit(self.db)
        self.db.refresh(org)

        return org

    def repair_organization_paths(self) -> Dict[str, int]:
        """回填缺失的组织 path/level（幂等；启动自检调用）。

        背景：早期经 API 直接 Organization(**org_data) 落库的组织 path/level 为
        NULL，而组织级数据权限完全依赖 path 前缀匹配 —— 这类组织的成员会被一律
        判定"无组织权限"。按 id 升序（父先于子）单趟回填即可收敛：父级在本轮
        已写入新 path，子级直接复用，无需多轮迭代。

        Returns:
            {"repaired": 本次回填条数, "remaining": 回填后仍为 NULL 的条数}
        """
        orgs = self.db.query(Organization).order_by(Organization.id).all()
        by_id = {org.id: org for org in orgs}
        repaired = 0
        for org in orgs:
            parent = by_id.get(org.parent_id) if org.parent_id else None
            expected_path = (
                f"{parent.path}{org.id}/"
                if parent is not None and parent.path
                else f"/{org.id}/"
            )
            expected_level = len([seg for seg in expected_path.split("/") if seg])
            if org.path != expected_path or str(org.level) != str(expected_level):
                org.path = expected_path
                org.level = expected_level
                repaired += 1
        if repaired:
            safe_commit(self.db)
        remaining = self.db.query(Organization).filter(Organization.path.is_(None)).count()
        return {"repaired": repaired, "remaining": remaining}

    def would_create_cycle(self, org_id: int, new_parent_id: Optional[int]) -> bool:
        """判断把 ``org_id`` 挂到 ``new_parent_id`` 之下是否会形成环。

        沿 ``new_parent_id`` 的**父链逐级上溯**（不是查 path —— path 在组织被移动后
        可能尚未刷新，用它做防环判定不可靠）。上溯过程自带 visited 去重：即使库中
        已因历史缺陷存在环，也不会死循环。

        Args:
            org_id: 被移动的组织 id
            new_parent_id: 目标父级 id（None / 0 表示置为顶级，永远合法）

        Returns:
            True 表示新父级是自身或自身的子孙（必须拒绝）
        """
        if not new_parent_id:
            return False
        visited: set = set()
        cursor: Optional[int] = new_parent_id
        while cursor and cursor not in visited:
            if cursor == org_id:
                return True
            visited.add(cursor)
            node = self.db.query(Organization).filter(Organization.id == cursor).first()
            cursor = node.parent_id if node else None
        return False

    def recompute_subtree_paths(self, root: Organization) -> int:
        """重算 ``root`` 及其全部子孙的 ``path`` / ``level``（移动或改父级后必须调用）。

        背景：组织级数据权限完全依赖 path 前缀匹配
        （``Organization.path.like(f"{org.path}%")``）。改父级却不刷新 path，会让
        「树视图（parent_id）」与「权限视图（path）」长期背离 —— 表现为移动后的
        组织看不到自己的下级数据、或仍能看到原父级的兄弟数据。

        - 采用广度优先：父级先于子级被处理，子级直接复用父级刚写入的 path，单趟收敛。
        - 与 ``create_organization`` / ``repair_organization_paths`` 保持同一套口径：
          ``path = 父.path + 本节点id + "/"``（根为 ``/{id}/``），``level = path 段数``。
        - visited 去重：库中若已存在环也不会死循环（只跳过重复节点）。

        Returns:
            被改写的组织条数（0 表示原本就是正确的）
        """
        changed = 0
        visited: set = set()
        queue: List[Organization] = [root]
        while queue:
            node = queue.pop(0)
            if node.id in visited:
                continue
            visited.add(node.id)

            parent = (
                self.db.query(Organization).filter(Organization.id == node.parent_id).first()
                if node.parent_id
                else None
            )
            expected_path = (
                f"{parent.path}{node.id}/"
                if parent is not None and parent.path
                else f"/{node.id}/"
            )
            expected_level = len([seg for seg in expected_path.split("/") if seg])
            if node.path != expected_path or str(node.level) != str(expected_level):
                node.path = expected_path
                node.level = expected_level
                changed += 1

            children = self.db.query(Organization).filter(Organization.parent_id == node.id).all()
            queue.extend(children)
        return changed

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
        if not org.path:
            # 历史数据兼容：早期经 API 直建的组织 path 为 NULL（前缀匹配必然
            # 落空 → include_self=True 也返回空集 → 组织级数据权限把该组织成员
            # 一律判为无权限）。此处退化为"仅自身"，配合
            # repair_organization_paths() 的启动回填逐步自愈。
            return [org] if include_self else []
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

        # 从路径解析祖先ID。
        # path 允许为 NULL（早期经 API 直写 Organization(**data) 落库的组织，
        # 见 repair_organization_paths 的说明），也可能含非数字脏段
        # （父级 path 为 NULL 时曾拼出 "None123/"）—— 解析失败一律按"无上级"
        # 处理，绝不让历史脏数据升级成 500。
        path_ids: List[int] = []
        for id_str in (org.path or "").strip("/").split("/"):
            if not id_str:
                continue
            try:
                path_ids.append(int(id_str))
            except (TypeError, ValueError):
                logger.warning(
                    "组织 %s 的 path 含非法段 %r，按无上级处理", org_id, id_str
                )
                return []

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
        by_level: dict[Any, Any] = {}
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
        """验证父子关系是否有效（防止循环引用）

        2026-10-14：判据统一到 ``would_create_cycle``（沿父链上溯），不再用
        ``get_subordinate_ids`` 的 path 前缀比对 —— 组织被移动后 path 可能尚未刷新，
        用 path 判环会漏判。对外语义保持不变（自身/不存在的子级一律 False）。

        Args:
            parent_id: 父组织ID
            child_id: 子组织ID

        Returns:
            关系是否有效
        """
        if parent_id == child_id:
            return False
        if not self.get_organization(child_id):
            return False
        return not self.would_create_cycle(child_id, parent_id)

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
