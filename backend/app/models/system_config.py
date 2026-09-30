"""
系统配置模型
"""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base


class SystemConfig(Base):
    """系统配置表"""

    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True, comment="配置键")
    value = Column(Text, comment="配置值")
    description = Column(String(200), comment="配置说明")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self):
        # SystemConfig 存 encryption_salt / verify_hash 等敏感值：repr 会被日志、
        # 调试器、异常回溯原样打印，绝不回显 value（深审 LIVE），只给长度。
        _value_len = len(self.value) if self.value else 0
        return f"<SystemConfig(key='{self.key}', value=<{_value_len} chars>)>"


class SystemUpdateLog(Base):
    """系统更新日志表"""

    __tablename__ = "system_update_logs"

    id = Column(String(50), primary_key=True)
    version = Column(String(50), nullable=False, comment="版本号")
    description = Column(Text, comment="更新内容描述")
    updated_by = Column(String(50), comment="更新人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    def to_dict(self):
        return {
            "id": self.id,
            "version": self.version,
            "description": self.description,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
