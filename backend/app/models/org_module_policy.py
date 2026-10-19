"""组织级模块策略模型

上级单位对下级单位系统的功能模块可见性与编辑权限管控。
通过管控配置包下发到下级单机系统执行。
"""

from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.models.base import BaseModel


class OrgModulePolicy(BaseModel):
    """组织模块策略表

    记录上级单位为某个下级组织设定的模块管控策略。
    每条记录对应一个 (organization_id, module_key) 组合。
    """

    __tablename__ = "org_module_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "module_key", name="uq_org_module"),
    )

    organization_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="目标下级组织ID",
    )
    module_key = Column(
        String(64),
        nullable=False,
        index=True,
        comment="模块标识（如 funds, projects, map）",
    )
    visibility = Column(
        String(20),
        default="visible",
        nullable=False,
        server_default="visible",
        comment="可见性: visible-可见, hidden-隐藏",
    )
    edit_mode = Column(
        String(20),
        default="full_edit",
        nullable=False,
        server_default="full_edit",
        comment="编辑模式: full_edit-完全编辑, read_only-只读, disabled-禁用",
    )
    created_by = Column(
        Integer,
        nullable=True,
        comment="创建人用户ID",
    )


# 静态模块定义（非DB，供 API 和前端使用）
MODULE_DEFINITIONS = [
    {"key": "dashboard", "name": "工作台", "category": "core"},
    {"key": "supported-villages", "name": "帮扶村管理", "category": "business"},
    {"key": "projects", "name": "项目管理", "category": "business"},
    {"key": "funds", "name": "资金管理", "category": "business"},
    {"key": "schools", "name": "学校管理", "category": "business"},
    {"key": "rural-works", "name": "乡村工作", "category": "business"},
    {"key": "policies", "name": "政策管理", "category": "business"},
    {"key": "organizations", "name": "组织管理", "category": "business"},
    {"key": "analytics", "name": "数据分析", "category": "analysis"},
    {"key": "map", "name": "态势地图", "category": "analysis"},
    {"key": "reports", "name": "报表中心", "category": "analysis"},
    {"key": "data-package", "name": "数据包管理", "category": "data"},
    {"key": "data-sync", "name": "数据同步", "category": "data"},
    {"key": "messages", "name": "消息中心", "category": "core"},
    {"key": "system", "name": "系统管理", "category": "system"},
]
