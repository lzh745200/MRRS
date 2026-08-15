"""
组织编码服务

提供组织编码的管理功能
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session


class OrganizationCodeService:
    """
    组织编码服务

    管理组织的编码体系
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._codes = {}

    def generate_code(
        self,
        org_name: str = "",
        parent_code: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> str:
        """生成组织编码；提供 prefix 时返回 ``PREFIX-XXXXXXXX`` 形态"""
        import hashlib
        import secrets

        base = f"{org_name}:{parent_code or ''}:{secrets.token_hex(4)}"
        code = hashlib.sha256(base.encode()).hexdigest()[:8].upper()
        if prefix:
            code = f"{prefix}-{code}"
        # 防止碰撞：如果已存在则在末尾添加随机字符
        original_code = code
        attempts = 0
        while code in self._codes and attempts < 10:
            code = f"{original_code}{secrets.randbelow(10)}"
            attempts += 1
        return code

    def validate_code(self, code: str) -> bool:
        """验证组织编码"""
        return len(code) >= 4 and code.isalnum()

    def get_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """获取编码信息"""
        return self._codes.get(code)

    def register_code(self, code: str, info: Dict[str, Any]):
        """注册编码"""
        self._codes[code] = info
