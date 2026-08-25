"""
政策法规服务层
提供政策法规的CRUD操作和查询功能
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.core.transaction import safe_commit
from app.schemas.policy import (
    CATEGORY_NAMES,
    LOCAL_LEVEL_NAMES,
    MILITARY_LEVEL_NAMES,
    STATUS_NAMES,
    CategoriesResponse,
    CategoryConfig,
    CategoryLevelConfig,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
)

logger = logging.getLogger(__name__)


class PolicyService:
    """政策法规服务"""

    def __init__(self, db: Session):
        self.db = db

    def _to_response(self, policy: Policy) -> PolicyResponse:
        """转换为响应对象"""
        if policy.category == "military":
            level_name = MILITARY_LEVEL_NAMES.get(policy.level, policy.level)
        else:
            level_name = LOCAL_LEVEL_NAMES.get(policy.level, policy.level)

        return PolicyResponse(
            id=policy.id,
            title=policy.title,
            content=policy.content,
            issue_date=policy.issue_date,
            effective_date=policy.effective_date,
            expiry_date=policy.effective_date,
            category=policy.category,
            level=policy.level,
            issuing_authority=policy.issuing_authority,
            summary=policy.summary,
            code=policy.code,
            file_path=policy.file_path,
            status=policy.status,
            keywords=policy.keywords,
            view_count=policy.view_count,
            download_count=policy.download_count,
            is_important=policy.is_important,
            file_size=policy.file_size,
            file_type=policy.file_type,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            created_by=None,
            updated_by=None,
            category_name=CATEGORY_NAMES.get(policy.category, policy.category),
            level_name=level_name,
            status_name=STATUS_NAMES.get(policy.status, policy.status),
        )

    def create_policy(self, data: PolicyCreate, user_id: Optional[int] = None) -> PolicyResponse:
        """创建政策"""
        policy = Policy(
            title=data.title,
            category=(data.category.value if hasattr(data.category, "value") else data.category),
            level=data.level,
            issuing_authority=data.issuing_authority,
            issue_date=data.issue_date,
            effective_date=data.effective_date,
            code=data.code,
            file_path=data.file_path,
            content=data.content,
            summary=data.summary,
            status=data.status.value if hasattr(data.status, "value") else data.status,
            keywords=data.keywords,
        )

        self.db.add(policy)
        safe_commit(self.db)
        self.db.refresh(policy)

        logger.info(f"Created policy: id={policy.id}, title={policy.title}")

        return self._to_response(policy)

    def get_policy_by_id(self, policy_id: int) -> Optional[PolicyResponse]:
        """获取单个政策详情"""
        policy = self.db.query(Policy).filter(Policy.id == policy_id).first()
        if not policy:
            return None
        return self._to_response(policy)

    def get_policy_model_by_id(self, policy_id: int) -> Optional[Policy]:
        """获取政策模型对象（内部使用）"""
        return self.db.query(Policy).filter(Policy.id == policy_id).first()

    def update_policy(
        self, policy_id: int, data: PolicyUpdate, user_id: Optional[int] = None
    ) -> Optional[PolicyResponse]:
        """更新政策"""
        policy = self.db.query(Policy).filter(Policy.id == policy_id).first()
        if not policy:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                # 处理枚举值
                if hasattr(value, "value"):
                    value = value.value
                setattr(policy, key, value)

        policy.updated_by = user_id

        safe_commit(self.db)
        self.db.refresh(policy)

        logger.info(f"Updated policy: id={policy.id}, title={policy.title}")

        return self._to_response(policy)

    def delete_policy(self, policy_id: int) -> bool:
        """删除政策"""
        policy = self.db.query(Policy).filter(Policy.id == policy_id).first()
        if not policy:
            return False

        logger.info(f"Deleting policy: id={policy.id}, title={policy.title}")

        self.db.delete(policy)
        safe_commit(self.db)
        return True

    def get_policies(
        self,
        skip: int = 0,
        limit: int = 10,
        category: Optional[str] = None,
        organization_level: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        order_by: str = "issue_date",
        order_desc: bool = True,
    ) -> Tuple[List[PolicyResponse], int]:
        """
        获取政策列表

        Args:
            skip: 跳过记录数
            limit: 每页记录数
            category: 分类筛选
            organization_level: 层级筛选
            status: 状态筛选
            search: 搜索关键词（搜索标题和内容）
            order_by: 排序字段
            order_desc: 是否降序

        Returns:
            Tuple[List[PolicyResponse], int]: (数据列表, 总数)
        """
        query = self.db.query(Policy)

        # 分类筛选
        if category:
            query = query.filter(Policy.category == category)

        # 层级筛选
        if organization_level:
            query = query.filter(Policy.level == organization_level)

        # 状态筛选
        if status:
            query = query.filter(Policy.status == status)

        # 关键词搜索（搜索标题和内容）
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Policy.title.ilike(search_pattern),
                    Policy.content.ilike(search_pattern),
                )
            )

        # 获取总数
        total = query.count()

        # 排序
        order_column = getattr(Policy, order_by, Policy.issue_date)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # 分页
        policies = query.offset(skip).limit(limit).all()

        return [self._to_response(p) for p in policies], total

    def get_related_policies(self, policy_id: int, limit: int = 5) -> List[PolicyResponse]:
        """
        获取相关政策（同分类同层级的其他政策）

        Args:
            policy_id: 当前政策ID
            limit: 返回数量限制

        Returns:
            List[PolicyResponse]: 相关政策列表
        """
        # 获取当前政策
        current_policy = self.db.query(Policy).filter(Policy.id == policy_id).first()
        if not current_policy:
            return []

        # 查询同分类同层级的其他政策
        query = (
            self.db.query(Policy)
            .filter(
                Policy.id != policy_id,
                Policy.category == current_policy.category,
                Policy.level == current_policy.level,
                Policy.status == "active",  # 只返回有效的政策
            )
            .order_by(Policy.issue_date.desc())
            .limit(limit)
        )

        policies = query.all()
        return [self._to_response(p) for p in policies]

    def increment_view_count(self, policy_id: int) -> bool:
        """增加浏览次数（W2-T6：原子 UPDATE）"""
        from sqlalchemy import func

        updated = (
            self.db.query(Policy)
            .filter(Policy.id == policy_id)
            .update({Policy.view_count: func.coalesce(Policy.view_count, 0) + 1})
        )
        if not updated:
            return False
        safe_commit(self.db)
        return True

    def get_categories(self) -> CategoriesResponse:
        """获取政策分类和层级配置"""
        return CategoriesResponse(
            military=CategoryConfig(
                name="专项政策",
                levels=[
                    CategoryLevelConfig(value="cmc", label="中央", order=1),
                    CategoryLevelConfig(value="provincial_military", label="省级", order=2),
                    CategoryLevelConfig(value="military_sub_district", label="市级", order=3),
                    CategoryLevelConfig(value="armed_forces_dept", label="区县级", order=4),
                ],
            ),
            local=CategoryConfig(
                name="地方政策",
                levels=[
                    CategoryLevelConfig(value="national", label="国家", order=1),
                    CategoryLevelConfig(value="provincial", label="省", order=2),
                    CategoryLevelConfig(value="prefecture", label="州", order=3),
                    CategoryLevelConfig(value="county", label="县 / 市", order=4),
                ],
            ),
        )

    def get_statistics_by_category(self) -> Dict[str, Any]:
        """获取按分类和层级的统计数据"""
        # 按分类统计
        category_counts = (
            self.db.query(Policy.category, func.count(Policy.id))
            .filter(Policy.status == "active")
            .group_by(Policy.category)
            .all()
        )

        # 按分类和层级统计
        level_counts = (
            self.db.query(Policy.category, Policy.level, func.count(Policy.id))
            .filter(Policy.status == "active")
            .group_by(Policy.category, Policy.level)
            .all()
        )

        # 构建统计结果
        result = {
            "military": {"total": 0, "levels": {}},
            "local": {"total": 0, "levels": {}},
        }

        for cat, count in category_counts:
            if cat in result:
                result[cat]["total"] = count

        for cat, level, count in level_counts:
            if cat in result:
                result[cat]["levels"][level] = count

        return result

    def batch_delete(self, policy_ids: List[int]) -> int:
        """批量删除政策"""
        deleted = self.db.query(Policy).filter(Policy.id.in_(policy_ids)).delete(synchronize_session=False)
        safe_commit(self.db)

        logger.info(f"Batch deleted {deleted} policies")

        return deleted
