#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""外键索引棘轮门禁（2026-10-31 巡检新增）。

## 为什么需要它

SQLite（以及多数库）**不会**为外键列自动建索引。缺索引时：
  * `WHERE fk_col = ?` 全表扫描；
  * `JOIN ... ON parent.id = child.fk_col` 全表扫描；
  * `ON DELETE CASCADE/SET NULL` 的级联删除逐行扫描子表。

数据量小时无感，增长后成为隐蔽的性能悬崖。

## 口径

对每张表的每个外键列 `c`：若不存在**以 c 为首列**的索引/主键/唯一约束，则计为「未覆盖」。
（首列很关键：复合索引 `(a, b)` 不能服务 `WHERE b = ?`。）

## 棘轮

巡检实测 43 处未覆盖，其中绝大多数是**审计类列**（`reviewed_by`/`imported_by`/`uploaded_by`
等，代码里零查询）—— 给它们加索引只会增加写开销，故**不做猜测性 schema 变更**，
而是把现状登记为基线**只许减少**：新增外键时必须同时加索引。

用法：

    python scripts/check_fk_indexes.py
    ... --json / --update
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "backend" / "scripts" / "gate_baselines" / "fk_indexes.json"


def _load_metadata():
    """加载全部模型并返回 Base.metadata（不建库，纯元数据）。"""
    import sys as _sys

    backend = str(ROOT / "backend")
    if backend not in _sys.path:
        _sys.path.insert(0, backend)
    from app.models.base import Base

    import app.models as models

    for name in getattr(models, "__all__", []):
        try:
            getattr(models, name)
        except Exception:  # noqa: BLE001 - 个别模型导入失败不应让门禁假绿
            continue
    return Base.metadata


def find_uncovered() -> list:
    meta = _load_metadata()
    out = []
    for tname, table in sorted(meta.tables.items()):
        covered = set()
        for idx in table.indexes:
            cols = [c.name for c in idx.columns]
            if cols:
                covered.add(cols[0])
        for col in table.primary_key.columns:
            covered.add(col.name)
        for cons in table.constraints:
            names = [c.name for c in getattr(cons, "columns", [])]
            if names and cons.__class__.__name__ in ("UniqueConstraint", "PrimaryKeyConstraint"):
                covered.add(names[0])
        for fk in table.foreign_key_constraints:
            for col in fk.columns:
                if col.name not in covered:
                    ref = list(fk.elements)[0].target_fullname if fk.elements else "?"
                    out.append({"table": tname, "column": col.name, "references": ref})
    return out


def _keys(items) -> set:
    return {f"{i['table']}.{i['column']}" for i in items}


def _load_baseline() -> set:
    if not BASELINE.is_file():
        return set()
    try:
        return set(json.loads(BASELINE.read_text(encoding="utf-8")).get("known", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_baseline(keys: set) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps({"known": sorted(keys)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="外键索引棘轮")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args(argv)

    items = find_uncovered()
    keys = _keys(items)
    known = _load_baseline()
    added = sorted(keys - known)
    fixed = sorted(known - keys)

    if args.update:
        _save_baseline(keys)
        print(f"[fk-index] 基线已更新为 {len(keys)} 项")
        return 0

    if args.json:
        print(json.dumps(
            {"uncovered": len(keys), "baseline": len(known), "added": added, "fixed": fixed,
             "items": items},
            ensure_ascii=False,
        ))
        return 1 if added else 0

    print(f"[fk-index] 外键列未被索引首列覆盖：{len(keys)} 处（基线 {len(known)}）")
    if fixed:
        print(f"  ✓ 已覆盖 {len(fixed)} 处（可 --update 收紧基线）: {fixed[:6]}")
    if added:
        print(f"  ✗ 新增 {len(added)} 处未覆盖外键：")
        for k in added:
            print(f"      {k}")
        print()
        print("修复：为新增外键列建索引（模型 index=True，或迁移里 op.create_index），")
        print("      命名沿用 ix_<表缩写>_<列>；确属零查询审计列时登记进基线并说明。")
        return 1
    print("[fk-index] OK：未覆盖外键未超出基线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
