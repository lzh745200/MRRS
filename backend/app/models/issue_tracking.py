"""Issue tracking models.

W27 P1（死模型清理，迁移 r41_drop_issues_001）：

**`Issue` 模型（表 `issues`）已删除** —— 实测全仓零生产引用：
* 无任何端点/服务使用它（`/feedback` 端点只用 `Feedback`）；
* 前端无对应页面；
* 它自带的 6 个"扩展字段"（`steps_to_reproduce` / `expected_behavior` /
  `actual_behavior` / `version_found` / `version_fixed` / `assignee`）本就零引用
  —— 它们是"问题追踪"功能只做了一半留下的骨架。

删除整表而非只删字段：`issues` 表除了这些死字段只剩
`title`/`description`/`priority`/`status`/`category`/`reporter`/`tags`/
`severity`/`environment`，而**没有任何写入路径** —— 保留一张永远为空的表
只会让人误以为"问题追踪"功能可用。

**`Feedback` 模型（表 `feedback`）保留** —— 它是**活的功能**：
`api/v1/feedback.py` 的 `GET/POST /api/v1/feedback` 已注册并在用。
其未接线的扩展字段（`rating` / `device_info` / `responded_at` / `responded_by`）
属"已实现功能的可扩展点"，**不是死字段** —— 接线它们比删除它们更有价值
（例如 `responded_at`/`responded_by` 对应"反馈回复"这一常见运营动作）。
"""

from sqlalchemy import Column, Index, Integer, String, Text

from .base import BaseModel, UtcDateTime


class Feedback(BaseModel):
    """User feedback model."""

    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_status_priority", "status", "priority"),
        Index("ix_feedback_user_id", "user_id"),
    )

    category = Column(String(50), nullable=False, index=True, comment="反馈分类")
    content = Column(Text, nullable=False, comment="反馈内容")
    priority = Column(String(20), nullable=False, index=True, comment="优先级")
    status = Column(String(20), nullable=False, index=True, comment="状态")

    # User information
    user_id = Column(String(100), comment="用户ID")
    user_email = Column(String(200), comment="用户邮箱")
    user_name = Column(String(100), comment="用户名")

    # Rating and metadata
    rating = Column(Integer, comment="评分(1-5)")
    source = Column(String(50), comment="反馈来源")
    device_info = Column(String(200), comment="设备信息")

    # Response tracking
    response = Column(Text, comment="回复内容")
    responded_at = Column(UtcDateTime(), comment="回复时间")
    responded_by = Column(String(100), comment="回复人")

    def __repr__(self):
        return (
            f"<Feedback(id={self.id}, category='{self.category}', "
            f"priority='{self.priority}', status='{self.status}')>"
        )
