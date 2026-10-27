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
        """由 6 位行政区划代码推断层级；非法返回 None。

        2026-10-27 起**以权威区划表为准**（`admin_division_service`：存在性 + 层级），
        表未覆盖的代码才退回「末位规律」（XX0000 / XXYY00 / XXYYZZ）。
        这样即便某地代码的末两位不遵循常规（区划调整、省直辖县等），也按表定为正确层级。
        """
        cleaned = str(code or "").strip()
        if len(cleaned) != ADMIN_AREA_CODE_LENGTH or not cleaned.isdigit():
            return None
        from app.services.admin_division_service import AdminDivisionService

        table_level = AdminDivisionService.level_key_of(cleaned)
        if table_level:
            return table_level
        if cleaned[2:] == "0000":
            return "level_1"
        if cleaned[4:] == "00":
            return "level_2"
        return "level_3"

    @staticmethod
    def validate_admin_code(code: str, parent_code: Optional[str] = None) -> str:
        """权威校验（存在性 + 层级 + 父子一致），返回归一化后的代码。

        与 ``normalize_admin_code``（只查格式）的分工：
        - ``normalize_admin_code``：长度/字符/别名归一，供「只关心格式」的旧调用点使用；
        - ``validate_admin_code``：组织创建/初始化等**落库路径**必须用它 ——
          它会拒绝不存在的代码（贵州全省全量校验），并校验子码与父码同属一个区划。
        """
        from app.services.admin_division_service import AdminDivisionService

        return AdminDivisionService.validate_code(code, parent_code)

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
