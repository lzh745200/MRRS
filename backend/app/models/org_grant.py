"""单位授权矩阵模型（R33）

上级单位把「模块 × 级别」授权物化后，经离线授权包下发；下级导入即只读执行。

为什么不是「绑到用户」：下级单位没有超级管理员、且完全离线，逐用户配置不可维护。
授权以**单位**为粒度，单位内用户共享同一份矩阵；个例差异仍走 `users.allowed_menus`
（最高优先级，本次不改）。

解析与裁决的唯一入口：`app.services.effective_grant_service`。
"""

from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.models.base import BaseModel

# 合法授权级别。语义：
#   edit - 可见且可写
#   view - 可见但只读（写接口返回 403）
#   none - 不可见（菜单不下发、路由 403、写接口 403）
VALID_GRANT_LEVELS = frozenset({"view", "edit", "none"})

# 级别强弱序：合并时「深者优先」，同层冲突时 deny 胜出
LEVEL_RANK = {"none": 0, "view": 1, "edit": 2}

DEFAULT_GRANT_LEVEL = "none"


class OrgGrant(BaseModel):
    """单位授权矩阵表

    每条记录对应一个 `(organization_id, module_key)` 组合，`level` 为该模块的授权级别。
    单位无任何记录 = 未授权（解析时回落到 legacy 路径，见 effective_grant_service）。
    """

    __tablename__ = "org_grants"
    __table_args__ = (
        UniqueConstraint("organization_id", "module_key", name="uq_org_grant"),
    )

    organization_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="目标单位ID（organizations.id）",
    )
    module_key = Column(
        String(64),
        nullable=False,
        index=True,
        comment="模块/菜单标识（与 MENU_DEFINITIONS 的 key 同源）",
    )
    level = Column(
        String(8),
        nullable=False,
        default=DEFAULT_GRANT_LEVEL,
        server_default=DEFAULT_GRANT_LEVEL,
        comment="授权级别: edit-可写, view-只读, none-不可见",
    )

    def __repr__(self) -> str:
        return (
            f"<OrgGrant(org={self.organization_id}, module='{self.module_key}', "
            f"level='{self.level}')>"
        )
