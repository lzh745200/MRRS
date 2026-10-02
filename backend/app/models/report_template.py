"""
ReportTemplate Model - 报表模板
上级可创建模板并分配给下级；下级在报表填报页面下载模板、填写、上传
上传时后端解析 Excel，根据 fields 映射自动导入到对应模块数据表
"""

from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, UtcDateTime

from .user import User  # noqa: F401 - relationship 字符串引用注册


class TemplateType(str, Enum):
    """模板类型"""

    import_template = "import"  # 导入模板
    export_template = "export"  # 导出模板


class TemplateModule(str, Enum):
    """关联模块"""

    village = "village"
    school = "school"
    fund = "fund"
    project = "project"
    rural_work = "rural_work"
    comprehensive = "comprehensive"


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # 模板名称
    name = Column(String(200), nullable=False)
    # 模板类型（使用 String 存储，兼容前端直接传入 "import"/"export" 字符串）
    type = Column(String(50), nullable=False)
    # 关联模块（使用 String 存储，兼容前端直接传入模块名字符串）
    module = Column(String(50), nullable=False, index=True)
    # 字段映射（JSON）- 定义 Excel 列与数据库字段的对应关系
    # 如: [{"excel_col": "A", "excel_header": "村名", "db_field": "village_name", "required": true}]
    fields = Column(Text, nullable=True)  # JSON string
    # 格式配置（JSON）- 纸张大小、页眉页脚、列宽等
    format_config = Column(Text, nullable=True)  # JSON string
    # 模板描述
    description = Column(String(500), nullable=True)
    # 模板文件路径（Excel模板文件）
    file_path = Column(String(500), nullable=True)
    # 是否启用
    is_active = Column(Boolean, default=True, nullable=False)
    # 创建人
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # 审计
    created_at = Column(UtcDateTime(), server_default=func.now())
    updated_at = Column(UtcDateTime(), server_default=func.now(), onupdate=func.now())

    # 关系
    creator = relationship("User", backref="report_templates")
