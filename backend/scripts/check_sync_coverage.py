#!/usr/bin/env python
"""同步链覆盖率门禁（W27 P1）—— 防「新表忘了进同步链」再次发生。

## 为什么需要

W26 全栈检测 P0-6 的**根因**：`data_reports`（上报台账）**不在任何同步链**。
`data_package_service.DATA_TYPE_MODELS` 与 `data_sync_service._SYNC_TABLE_LABELS`
都没有它，而它是唯一创建点 —— 多机部署下上级机永远收不到下级上报。
这类缺陷**不会报错、不会变红**，只会让功能静默不成立；靠人工记忆维护两张清单
迟早再次漏掉。

## 判定口径（三层，任一不满足即失败）

1. **跨机业务表**（`MULTI_MACHINE_TABLES`）：必须至少出现在一条同步链
   （数据包链 `DATA_TYPE_MODELS` / 增量同步链 `_SYNC_TABLE_LABELS`）**或**
   有明确的特殊通道（`SPECIAL_CHANNELS`，如上报台账走规范化台账）。
2. **特殊通道必须真的接线**：`SPECIAL_CHANNELS` 里的函数名必须能在源码中找到
   调用点（防"声明了但没实现"，这正是 P0-6 的原始形态）。
3. **不允许多机表落进"敏感表禁导"名单**：`_SENSITIVE_TABLES` 里的表若同时声明为
   跨机业务表，属自相矛盾配置，直接失败。

## 用法

    python scripts/check_sync_coverage.py           # 门禁（CI 用）
    python scripts/check_sync_coverage.py --list    # 打印当前覆盖率明细

退出码：0=通过，1=发现缺口。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_ROOT / "app"

# ── 跨机业务表：多机部署下必须能在机器之间传递的数据 ──────────────────
# 新增此类表时必须在此登记，并接入某一同步链（或声明特殊通道）。
MULTI_MACHINE_TABLES: dict[str, str] = {
    "supported_villages": "帮扶村主档",
    "village_population": "人口数据",
    "village_income": "收入数据",
    "organizations": "组织树（编码=行政区划代码，跨机唯一依据）",
    "policies": "政策库",
    "force_investment": "力量投入",
    "industry_support": "产业帮扶",
    "infrastructure_improvement": "基础设施",
    "party_building_support": "党建帮扶",
    "medical_support": "医疗帮扶",
    "consumption_support": "消费帮扶",
    "employment_support": "就业帮扶",
    "education_support": "教育帮扶",
    "projects": "帮扶项目",
    "funds": "帮扶经费",
    "schools": "帮扶学校",
    "data_reports": "上报台账（特殊通道：规范化台账 + 组织编码重映射）",
}

# ── 特殊通道：不是普通表同步，但确有跨机实现 ──────────────────────────
# value = 必须能在源码中作为**调用**出现的函数名（防"只声明没实现"）。
SPECIAL_CHANNELS: dict[str, tuple[str, str]] = {
    "data_reports": ("_export_report_ledger", "_import_report_ledger"),
}


def _read_module_source(name: str) -> str:
    path = APP_DIR / "services" / f"{name}.py"
    if not path.exists():
        raise SystemExit(f"[gate:sync_coverage] 找不到服务模块: {path}")
    # utf-8-sig：容忍 BOM（否则 ast.parse 抛 SyntaxError → 门禁假绿/崩溃）
    return path.read_text(encoding="utf-8-sig")


def _dict_literal_keys(source: str, var_name: str) -> set[str]:
    """从模块源码中解析 `var_name = { "k": ... }` 的字符串键集合（AST，不执行代码）。"""
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == var_name:
                value = node.value
                keys: set[str] = set()
                if isinstance(value, ast.Dict):
                    for k in value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
                elif isinstance(value, (ast.Set, ast.List, ast.Tuple)):
                    for elt in value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            keys.add(elt.value)
                # 允许 `dict(A=X, B=Y)` 形态
                elif isinstance(value, ast.Call):
                    for kw in value.keywords:
                        if kw.arg:
                            keys.add(kw.arg)
                return keys
    return set()


def _function_called(source: str, func_name: str) -> bool:
    """函数名是否以**调用**形式出现（`foo(`），排除仅定义/仅注释。"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == func_name:
                return True
            if isinstance(fn, ast.Name) and fn.id == func_name:
                return True
    return False


def main(argv: list[str]) -> int:
    list_only = "--list" in argv

    pkg_src = _read_module_source("data_package_service")
    sync_src = _read_module_source("data_sync_service")

    package_chain = _dict_literal_keys(pkg_src, "DATA_TYPE_MODELS")
    sync_chain = _dict_literal_keys(sync_src, "_SYNC_TABLE_LABELS")
    sensitive = _dict_literal_keys(sync_src, "_SENSITIVE_TABLES") | _dict_literal_keys(
        sync_src, "_SENSITIVE_TABLES".lstrip("_")
    )

    problems: list[str] = []
    rows: list[str] = []

    for table, label in sorted(MULTI_MACHINE_TABLES.items()):
        channels: list[str] = []
        if table in package_chain:
            channels.append("数据包链")
        if table in sync_chain:
            channels.append("增量同步链")
        special = SPECIAL_CHANNELS.get(table)
        if special:
            missing = [fn for fn in special if not _function_called(pkg_src + sync_src, fn)]
            if missing:
                problems.append(
                    f"{table}（{label}）声明了特殊通道但源码中未找到调用: {', '.join(missing)}"
                )
            else:
                channels.append("特殊通道")
        if table in sensitive:
            problems.append(
                f"{table}（{label}）同时被登记为「敏感表禁导」，配置自相矛盾"
            )
        if not channels:
            problems.append(
                f"{table}（{label}）不在任何同步链，也没有特殊通道 —— "
                "多机部署下该数据无法跨机传递（W26-P0-6 的原始形态）"
            )
        rows.append(f"  {table:<32} {'/'.join(channels) if channels else 'x 未覆盖'}")

    if list_only:
        print("[gate:sync_coverage] 跨机业务表覆盖明细：")
        print("\n".join(rows))
        print()
        print(f"[gate:sync_coverage] 数据包链 {len(package_chain)} 表 / 增量同步链 {len(sync_chain)} 表")
        return 0

    if problems:
        print(f"[gate:sync_coverage] 发现 {len(problems)} 处缺口：")
        for p in problems:
            print(f"  x {p}")
        return 1

    print(
        f"[gate:sync_coverage] OK: {len(MULTI_MACHINE_TABLES)} 张跨机业务表全部可达 "
        f"(数据包链 {len(package_chain)} / 增量同步链 {len(sync_chain)} / "
        f"特殊通道 {len(SPECIAL_CHANNELS)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
