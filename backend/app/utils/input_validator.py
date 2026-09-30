"""输入验证工具模块

提供XSS防护、SQL注入防护、格式验证等功能
"""

import html
import re
from typing import List, Optional

from fastapi import HTTPException, status


class InputValidator:
    """输入验证器"""

    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
    ]

    # 锚定到 SQL 语法结构，而不是裸关键词：原规则把 union|select|update|delete
    # 等词本身当注入特征，正常文本（"please update the record"）会被误判
    # （深审 #1）。
    SQL_INJECTION_PATTERNS = [
        r"\bunion\s+(all\s+)?select\b",
        r"\bselect\b[^\n]{0,80}?\bfrom\b",
        r"\binsert\s+into\b",
        r"\bupdate\s+\w+\s+set\b",
        r"\bdelete\s+from\b",
        r"\bdrop\s+(table|database|index|view|trigger)\b",
        r"\bcreate\s+(table|database|index|view|trigger|user)\b",
        r"\balter\s+table\b",
        r"\bexec(ute)?\s+\w",
        r"(--|#|/\*|\*/)",
        r"(\bor\b.*=.*\bor\b)",
        r"(\band\b.*=.*\band\b)",
    ]

    # 校验长度上限：正则回溯在超长输入上是 CPU 放大器（深审 #1）。
    MAX_SQL_CHECK_LENGTH = 4096

    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """清理字符串，防止XSS攻击

        Args:
            text: 输入文本
            max_length: 最大长度

        Returns:
            清理后的文本
        """
        if not isinstance(text, str):
            return str(text)

        text = text[:max_length]

        for pattern in InputValidator.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="输入包含不安全内容")

        # 用 html.escape 完整转义（含 & 与引号）：原先只替换尖括号，&lt;script&gt;
        # 原样通过，且 & 未转义会让输出无法安全嵌入 HTML 属性（深审 #2）。
        return html.escape(text, quote=True).strip()

    @staticmethod
    def validate_sql_safe(text: str) -> str:
        """验证SQL安全性

        Args:
            text: 输入文本

        Returns:
            验证后的文本
        """
        if not isinstance(text, str):
            return str(text)

        if len(text) > InputValidator.MAX_SQL_CHECK_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"输入过长（上限 {InputValidator.MAX_SQL_CHECK_LENGTH} 字符）",
            )

        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="检测到SQL注入风险")

        return text

    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """验证手机号格式"""
        pattern = r"^1[3-9]\d{9}$"
        return bool(re.match(pattern, phone))

    @staticmethod
    def validate_id_card(id_card: str) -> bool:
        """验证身份证号格式"""
        pattern = r"^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$"
        return bool(re.match(pattern, id_card))

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """验证文件扩展名"""
        if "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in allowed_extensions

    @staticmethod
    def validate_file_size(file_size: int, max_size_mb: int = 10) -> bool:
        """验证文件大小"""
        max_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_bytes

    @staticmethod
    def validate_number_range(value: float, min_val: Optional[float] = None, max_val: Optional[float] = None) -> bool:
        """验证数值范围"""
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    @staticmethod
    def validate_required_fields(data: dict, required_fields: List[str]) -> None:
        """验证必填字段"""
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]

        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"缺少必填字段: {', '.join(missing_fields)}",
            )
