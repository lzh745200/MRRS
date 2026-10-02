"""错误报告模型 — 持久化系统错误报告（替代内存存储）。"""

from sqlalchemy import Column, String, Text

from app.models.base import BaseModel, UtcDateTime


class ErrorReport(BaseModel):
    __tablename__ = "error_reports"

    source = Column(String(100), nullable=False, comment="错误来源模块")
    error_type = Column(String(100), nullable=False, comment="错误类型")
    message = Column(Text, nullable=False, comment="错误消息")
    stack_trace = Column(Text, nullable=True, comment="堆栈跟踪信息")
    context = Column(Text, nullable=True, comment="上下文信息(JSON)")
    severity = Column(String(20), default="warning", nullable=False, comment="严重程度: info/warning/error/critical")
    status = Column(String(20), default="open", nullable=False, comment="状态: open/resolved/ignored/in_progress")
    reporter = Column(String(100), nullable=True, comment="报告人")
    resolved_at = Column(UtcDateTime(), nullable=True, comment="解决时间")
    resolution_note = Column(Text, nullable=True, comment="处理备注")

    def to_dict(self, camel_case: bool = True):
        import json

        result = super().to_dict(camel_case=False)
        if result.get("context"):
            try:
                result["context"] = json.loads(result["context"])
            except (json.JSONDecodeError, TypeError):
                pass
        if camel_case:
            from app.utils.common import dict_keys_to_camel

            return dict_keys_to_camel(result)
        return result
