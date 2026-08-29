"""Issue tracking models."""

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from .base import BaseModel


class Issue(BaseModel):
    """Issue tracking model."""

    __tablename__ = "issues"

    __table_args__ = (
        Index("ix_issues_status_priority", "status", "priority"),
        Index("ix_issues_category_status", "category", "status"),
    )

    title = Column(String(200), nullable=False, index=True, comment="问题标题")
    description = Column(Text, nullable=False, comment="问题描述")
    steps_to_reproduce = Column(Text, comment="重现步骤")
    expected_behavior = Column(Text, comment="期望行为")
    actual_behavior = Column(Text, comment="实际行为")

    # Classification fields
    priority = Column(String(20), nullable=False, index=True, comment="优先级")
    status = Column(String(20), nullable=False, index=True, comment="状态")
    category = Column(String(50), nullable=False, index=True, comment="分类")

    # Assignment fields
    reporter = Column(String(100), nullable=False, comment="报告人")
    assignee = Column(String(100), comment="负责人")

    # Version tracking
    version_found = Column(String(50), nullable=False, index=True, comment="发现版本")
    version_fixed = Column(String(50), comment="修复版本")

    # Additional metadata
    tags = Column(String(500), comment="标签")
    severity = Column(String(20), comment="严重程度")
    environment = Column(String(100), comment="环境信息")

    def __repr__(self):
        return f"<Issue(id={self.id}, title='{self.title}', status='{self.status}', priority='{self.priority}')>"


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
    responded_at = Column(DateTime(timezone=True), comment="回复时间")
    responded_by = Column(String(100), comment="回复人")

    def __repr__(self):
        return (
            f"<Feedback(id={self.id}, category='{self.category}', "
            f"priority='{self.priority}', status='{self.status}')>"
        )
