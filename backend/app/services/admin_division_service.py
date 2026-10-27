# -*- coding: utf-8 -*-
"""行政区划权威表（离线）。

## 为什么要这张表（2026-10-27 体检）

组织编码 = 6 位行政区划代码，是**跨机匹配的唯一依据**。此前全系统只按「末两位规律」
（`XX0000` / `XXYY00` / `XXYYZZ`）推断层级，实测暴露出三类问题：

1. **不校验代码是否真实存在** —— `522799`、`999999` 都能入库并被判成「县市级」；
2. **不校验父子代码一致性** —— `522701`（都匀市）可以挂到 `520100`（贵阳市）下，
   组织树与按 path 前缀计算的**数据权限**会把黔南的县市算进贵阳子树；
3. **初始化只接受省级编码**（`XX0000`），市州级/县级单位（如黔南州 522700）无法首启。

故引入本表：**存在性 + 层级 + 父子关系**以表为准，末位规律仅对表未覆盖的代码兜底。

## 数据来源与覆盖范围

- 省级 34 个：GB/T 2260 省级编码（固定常量）；
- 贵州全省市州（9）与县级（88）：仓库内置 `frontend/src/assets/geo/guizhou.json`
  的官方 adcode（既有数据，已用于地图与报表）；
- `aliases`：已知区划调整换码（如 `520222` 盘县 → `520281` 盘州市）。

**覆盖策略**：贵州（`52` 前缀）为全量覆盖 —— 查不到即视为非法代码；
其它省份仅省级入表，市州/县级由末位规律兜底并标记 `verified=False`
（把国家统计局全量表按同一 schema 放进 `backend/app/data/admin_divisions.json`
即可自动升级为全量校验）。

本模块只依赖标准库，不做 IO 之外的副作用，可被服务层与端点层安全复用。
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "admin_divisions.json"

# 表内**全量覆盖**的省级前缀：该前缀下查不到 = 非法代码（而不是"未入表"）
FULLY_COVERED_PROVINCE_PREFIXES = ("52",)  # 贵州省

LEVEL_KEYS = {1: "level_1", 2: "level_2", 3: "level_3"}


def _load_raw() -> dict:
    """读原始 JSON；文件缺失/损坏时降级为空表并告警（绝不因数据文件崩启动）。"""
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # 未打包/被裁剪/内容损坏
        logger.warning(
            "行政区划权威表不可用（%s）：organization code 校验降级为末位规律，"
            "存在性与父子一致性将不被强制",
            exc,
        )
        return {}


@lru_cache(maxsize=1)
def _table() -> Dict[str, dict]:
    """加载并摊平权威表：code -> {name, level, parent}（进程内缓存）。"""
    raw = _load_raw()
    flat: Dict[str, dict] = {}
    for key, level in (("level1", 1), ("level2", 2), ("level3", 3)):
        for code, item in (raw.get(key) or {}).items():
            flat[code] = {
                "name": item.get("name"),
                "level": level,
                "parent": item.get("parent"),
            }
    return flat


@lru_cache(maxsize=1)
def _aliases() -> Dict[str, str]:
    raw = _load_raw()
    return {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}


class AdminDivisionService:
    """行政区划代码的权威查询与校验（组织编码的唯一口径来源）。"""

    # ── 查询 ──────────────────────────────────────────────────────────
    @staticmethod
    def resolve_alias(code: str) -> str:
        """已知换码归一化：旧码返回新码，其余原样返回。"""
        cleaned = str(code or "").strip()
        return _aliases().get(cleaned, cleaned)

    @staticmethod
    def lookup(code: str) -> Optional[dict]:
        """查表（自动走别名归一）。返回 {code, name, level, parent, verified}。"""
        cleaned = AdminDivisionService.resolve_alias(code)
        item = _table().get(cleaned)
        if item is None:
            return None
        return {
            "code": cleaned,
            "name": item.get("name"),
            "level": int(item.get("level") or 0),
            "parent": item.get("parent"),
            "verified": True,
        }

    @staticmethod
    def level_of(code: str) -> Optional[int]:
        """表内层级（1/2/3）；不在表内返回 None。"""
        item = AdminDivisionService.lookup(code)
        return item["level"] if item else None

    @staticmethod
    def level_key_of(code: str) -> Optional[str]:
        """表内层级键（level_1/2/3）；不在表内返回 None。"""
        level = AdminDivisionService.level_of(code)
        return LEVEL_KEYS.get(level) if level else None

    @staticmethod
    def name_of(code: str) -> Optional[str]:
        item = AdminDivisionService.lookup(code)
        return item["name"] if item else None

    @staticmethod
    def parent_of(code: str) -> Optional[str]:
        item = AdminDivisionService.lookup(code)
        return item["parent"] if item else None

    @staticmethod
    def is_covered(code: str) -> bool:
        """该代码所属省份是否在表内全量覆盖（查不到即可判定非法）。

        表不可用（未打包/损坏）时一律返回 False —— 降级为"仅末位规律"，
        绝不因为缺数据文件就把所有贵州组织编码判成非法。
        """
        if not _table():
            return False
        cleaned = AdminDivisionService.resolve_alias(code)
        return cleaned[:2] in FULLY_COVERED_PROVINCE_PREFIXES

    # ── 校验 ──────────────────────────────────────────────────────────
    @staticmethod
    def prefix_parent(code: str) -> Optional[str]:
        """按末位规律推出的父级代码（省级→None，市州→XX0000，县市→XXYY00）。"""
        cleaned = str(code or "").strip()
        if len(cleaned) != 6 or not cleaned.isdigit():
            return None
        if cleaned[2:] == "0000":
            return None
        if cleaned[4:] == "00":
            return cleaned[:2] + "0000"
        return cleaned[:4] + "00"

    @staticmethod
    def validate_code(code: str, parent_code: Optional[str] = None) -> str:
        """校验并返回归一化后的 6 位代码；不合法抛 ``ValueError``（中文可读原因）。

        规则（按优先级）：
        1. 格式：6 位纯数字（长度/字符错误 → 直接拒绝）；
        2. 别名：已知旧码自动换成新码；
        3. 存在性：表内覆盖的省份（贵州）必须能在表中查到，否则拒绝；
           未覆盖省份退回末位规律，标记 ``verified=False`` 放行；
        4. 父子一致：给了 ``parent_code`` 时，表内条目用**表中 parent** 比对；
           表外条目按前缀（县市比前 4 位、市州比前 2 位）比对。
        """
        cleaned = str(code or "").strip()
        if not cleaned:
            raise ValueError("组织编码（行政区划代码）不能为空")
        if not cleaned.isdigit():
            raise ValueError("组织编码必须是纯数字的行政区划代码（如 520000 / 522700 / 522701）")
        if len(cleaned) != 6:
            raise ValueError("组织编码必须是 6 位行政区划代码（如 520000 / 522700 / 522701）")

        resolved = AdminDivisionService.resolve_alias(cleaned)
        if resolved != cleaned:
            cleaned = resolved  # 旧码自动归一，后续按新码校验

        item = AdminDivisionService.lookup(cleaned)
        if item is None:
            if AdminDivisionService.is_covered(cleaned):
                raise ValueError(
                    f"行政区划代码 {cleaned} 不在权威区划表中（贵州省为全量校验）；"
                    "请核对国家统计局公布的最新 6 位代码"
                )
            # 未覆盖省份：退回末位规律
            if len(cleaned) != 6 or not cleaned.isdigit():
                raise ValueError("组织编码必须是 6 位纯数字的行政区划代码")
        else:
            expected_level = item["level"]
            pattern_level = AdminDivisionService.pattern_level(cleaned)
            if pattern_level and pattern_level != expected_level:
                raise ValueError(
                    f"行政区划代码 {cleaned} 的末位规律与权威表层级不一致"
                    f"（表内 {expected_level} 级 / 规律推得 {pattern_level} 级），请核对代码"
                )

        if parent_code:
            parent_clean = AdminDivisionService.resolve_alias(str(parent_code).strip())
            if item is not None and item.get("parent"):
                if parent_clean != item["parent"]:
                    parent_name = AdminDivisionService.name_of(parent_clean) or parent_clean
                    own_name = item.get("name") or cleaned
                    raise ValueError(
                        f"组织编码 {cleaned}（{own_name}）的上级应为 {item['parent']}，"
                        f"而不是 {parent_clean}（{parent_name}）"
                    )
            else:
                expected_parent = AdminDivisionService.prefix_parent(cleaned)
                if expected_parent and parent_clean != expected_parent:
                    raise ValueError(
                        f"组织编码 {cleaned} 与上级代码 {parent_clean} 不属同一行政区划"
                        f"（按代码规律上级应为 {expected_parent}）"
                    )
        return cleaned

    @staticmethod
    def pattern_level(code: str) -> Optional[int]:
        """按末位规律推出的层级：1=省 / 2=市州 / 3=县市（不查表）。"""
        cleaned = str(code or "").strip()
        if len(cleaned) != 6 or not cleaned.isdigit():
            return None
        if cleaned[2:] == "0000":
            return 1
        if cleaned[4:] == "00":
            return 2
        return 3

    @staticmethod
    def coverage() -> Dict[str, object]:
        """覆盖范围摘要（供自检/关于页展示）。"""
        table = _table()
        counts = {1: 0, 2: 0, 3: 0}
        for item in table.values():
            counts[int(item["level"])] += 1
        return {
            "level1": counts[1],
            "level2": counts[2],
            "level3": counts[3],
            "aliases": len(_aliases()),
            "fullyCoveredPrefixes": list(FULLY_COVERED_PROVINCE_PREFIXES),
        }
