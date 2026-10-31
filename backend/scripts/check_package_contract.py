#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据包清单（manifest）字段契约棘轮（P0-F3）。

跨机离线同步的生命线是 `schemas/data_package.py::DataPackageManifest`：
一旦某个字段被**删除/改名/改类型**，旧机关生成的包在新机关直接
「import 失败」或「manifest 校验不过」——此类损坏要等介质到了现场才发现。
本门禁把 manifest 的字段集合 + PackageType 枚举做成**快照对比**：
- 删除字段 / 改字段类型 / 改必填性 / 移除枚举值 → **红**（破坏性变更）；
- 新增字段/枚举值 → 视作**需要显式确认**的变更：必须人工 `--update` 入库基线，
  让 CONTRACT 变更在 PR 里可见，而不是随顺手 delete 进来。

用法:
    python backend/scripts/check_package_contract.py            # 校验
    python backend/scripts/check_package_contract.py --update   # 人工确认后写回基线
"""
from __future__ import annotations

import argparse
import enum
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts" / "gate_baselines" / "package_contract.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def _load_manifest_class():
    from app.schemas.data_package import DataPackageManifest, PackageType

    return DataPackageManifest, PackageType


def _enum_values(nm: enum.EnumMeta) -> list[str]:
    return sorted(str(member.value) for member in nm)


def contract_snapshot(manifest_cls, package_type_enum) -> dict:
    """生成当前 manifest 的快照（字段名 / 类型串 / 是否必填）。"""
    fields = {}
    for name, field in manifest_cls.model_fields.items():
        ann = str(field.annotation)
        required = field.is_required()
        fields[name] = {"annotation": ann, "required": required}
    return {
        "manifest_cls": "DataPackageManifest",
        "fields": fields,
        "package_type_values": _enum_values(package_type_enum),
    }


def diff_snapshot(baseline: dict, current: dict) -> list[str]:
    """返回破坏性/需要确认的变更列表（有序、可读）。"""
    problems: list[str] = []
    b_fields = baseline.get("fields", {})
    c_fields = current.get("fields", {})
    for name in sorted(set(b_fields) - set(c_fields)):
        problems.append(f"删除字段: {name}")
    for name in sorted(set(c_fields) - set(b_fields)):
        problems.append(f'新增字段: {name} ({c_fields[name]["annotation"]})')
    for name in sorted(set(b_fields) & set(c_fields)):
        before, after = b_fields[name], c_fields[name]
        if before["annotation"] != after["annotation"]:
            problems.append(
                f'字段类型变化: {name}: {before["annotation"]} -> {after["annotation"]}'
            )
        if before["required"] != after["required"]:
            problems.append(
                f'字段必填性变化: {name}: {before["required"]} -> {after["required"]}'
            )
    b_enums = baseline.get("package_type_values", [])
    c_enums = current.get("package_type_values", [])
    for v in sorted(set(b_enums) - set(c_enums)):
        problems.append(f"移除枚举值: PackageType.{v}")
    for v in sorted(set(c_enums) - set(b_enums)):
        problems.append(f"新增枚举值: PackageType.{v}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="数据包 manifest 契约棘轮")
    ap.add_argument("--update", action="store_true", help="把现状写回基线（破坏性变更人工确认后使用）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(ROOT / "backend") not in sys.path:
        sys.path.insert(0, str(ROOT / "backend"))

    # 需要能 import app.* —— 允许用数据库虚拟环境之外的环境，只要有 pydantic
    manifest_cls, package_type = _load_manifest_class()
    current = contract_snapshot(manifest_cls, package_type)

    if args.update:
        BASELINE.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f'[update] {BASELINE.relative_to(ROOT)} <- {len(current["fields"])} 字段 / {len(current["package_type_values"])} 枚举')
        return 0

    if not BASELINE.exists():
        print(f"[FAIL] 基线缺失: {BASELINE.relative_to(ROOT)} —— 先 --update 生成", file=sys.stderr)
        return 1
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    problems = diff_snapshot(baseline, current)
    if problems:
        for p in problems:
            print("  x", p)
        print("\n说明：以上是数据包 manifest 契约的**破坏性变更**。", file=sys.stderr)
        print("若属有意为之：运行 --update 并在 PR 里写明兼容性策略；否则请撤回字段改动。", file=sys.stderr)
        return 1
    print(f'[gate:package_contract] OK ({len(current["fields"])} fields / {len(current["package_type_values"])} enums)')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
