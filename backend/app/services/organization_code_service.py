"""
组织编码服务

提供组织编码的管理功能
"""

import re

from typing import Dict, Any, Optional

from sqlalchemy.orm import Session


# 行政区划代码（GB/T 2260）与组织层级的对应：省 2 位 / 市州 4 位 / 县市 6 位。
# 这是全系统唯一的"编码→层级"判定口径，禁止在其它模块重复实现。
# 行政区划代码（GB/T 2260）：统一 6 位数字，末位规律决定层级 ——
#   省级   XX0000（如 520000 贵州省）
#   市州级 XXYY00（如 520100 贵阳市）
#   县市级 XXYYZZ（如 520102 南明区）
# 这是全系统唯一的「编码→层级」判定口径，禁止在其它模块重复实现。
LEVEL_LABELS: Dict[str, str] = {
    "level_1": "省级单位",
    "level_2": "市州级单位",
    "level_3": "县市级单位",
}
LEVEL_ORDER: Dict[str, int] = {"level_1": 1, "level_2": 2, "level_3": 3}
ADMIN_AREA_CODE_LENGTH = 6
ADMIN_AREA_CODE_SUFFIX_HINTS: Dict[str, str] = {
    "level_1": "末四位为 0000（如 520000）",
    "level_2": "末两位为 00（如 520100）",
    "level_3": "末两位非 00（如 520102）",
}


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

    @staticmethod
    def normalize_admin_code(code: str) -> str:
        """校验并规范化行政区划代码；不合法时抛 ValueError（带可读原因）。

        规则：纯数字，长度必须是 2（省）/ 4（市州）/ 6（县市）之一。
        这是跨机匹配的唯一依据，因此不接受字母、短横线或其它长度。
        """
        cleaned = str(code or "").strip()
        if not cleaned:
            raise ValueError("组织编码（行政区划代码）不能为空")
        if not cleaned.isdigit():
            raise ValueError("组织编码必须是纯数字的行政区划代码（如 520000 / 520100 / 520102）")
        if len(cleaned) != ADMIN_AREA_CODE_LENGTH:
            raise ValueError("组织编码必须是 6 位行政区划代码（省级 XX0000 / 市州级 XXYY00 / 县市级 XXYYZZ）")
        return cleaned

    @staticmethod
    def infer_level(code: str) -> Optional[str]:
        """由 6 位行政区划代码的末位规律推断层级；非法返回 None。"""
        cleaned = str(code or "").strip()
        if len(cleaned) != ADMIN_AREA_CODE_LENGTH or not cleaned.isdigit():
            return None
        if cleaned[2:] == "0000":
            return "level_1"
        if cleaned[4:] == "00":
            return "level_2"
        return "level_3"

    @staticmethod
    def level_order(level: Any) -> Optional[int]:
        """层级转序号，兼容 level_N 与历史深度数字；无法识别返回 None。"""
        text = str(level or "").strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        if text in LEVEL_ORDER:
            return LEVEL_ORDER[text]
        m = re.fullmatch(r"level_(\d+)", text)
        return int(m.group(1)) if m else None

    def validate_code(self, code: str) -> bool:
        """验证组织编码（行政区划代码口径）。"""
        try:
            self.normalize_admin_code(code)
            return True
        except ValueError:
            return False

    def get_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """获取编码信息"""
        return self._codes.get(code)

    def register_code(self, code: str, info: Dict[str, Any]):
        """注册编码"""
        self._codes[code] = info
