#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""迁移自证门禁（2026-10-29 全库审计，对应审计项 C1「迁移基线自证」）。

## 它解决什么问题

`alembic/versions/001_baseline.py` 在核心表缺失时会 `Base.metadata.create_all()` ——
于是**新库在第一个迁移就落成"今天的模型"**，后面 62 个迁移靠存在性守卫几乎全部跳过。
后果：

1. 迁移脚本本身**从未在新库上被真正执行**；
2. `check_stack_alignment` 的 B 轴（模型 ↔ `alembic upgrade head` 空库）因此恒 0 漂移 ——
   因为参照库就是模型建的，属于**自证**；
3. 真实漂移只好靠人工发现。v1.18.26 的 PII 列宽就是这样漏的：模型 `EncryptedText(256)`、
   库里 `VARCHAR(20)`，而 B 轴只比列**存在性**、不比**类型/长度**，加上参照库由 create_all
   生成，完全看不出来。

## 本门禁的口径

不试图自动判定"迁移是否真的执行过"（不可判定），而是要求**会改变 schema 形状的迁移**
必须自带一个能独立构造「旧库状态」的测试文件 —— 即"迁移自证证据"。这类证据绕开了
create_all 短路，因为它在测试里手工建出旧结构再驱动迁移函数。

判定规则：

- 扫描 `alembic/versions/*.py`，识别含 `alter_column` / `drop_column` / `drop_table` /
  `create_index` / `drop_index` / `add_column` 的迁移；
- 要求存在 `backend/tests/unit/test_<revision 前缀>_*.py`（或 `test_migration_<前缀>_*.py`）；
- 历史上没有证据的迁移登记在 `backend/scripts/gate_baselines/migration_evidence.json`，
  **只对不在清单里的迁移严格**（棘轮式：新增必须带证据，历史不追溯）。

用法：

    backend/.venv/Scripts/python.exe scripts/check_migration_self_evidence.py
    ... --json      # 机器可读
    ... --update    # 把当前无证据的迁移加入豁免清单（仅限历史遗留，慎用）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "backend" / "alembic" / "versions"
TESTS = ROOT / "backend" / "tests" / "unit"
BASELINE = ROOT / "backend" / "scripts" / "gate_baselines" / "migration_evidence.json"

# 这些操作会改变 schema 形状，必须自带「旧库状态」证据
SHAPE_CHANGING = (
    "alter_column",
    "drop_column",
    "drop_table",
    "add_column",
    "create_index",
    "drop_index",
    "create_table",
)

_REVISION_RE = re.compile(r'^revision\s*=\s*["\']([^"\']+)["\']', re.M)


def _revision_of(path: Path) -> str | None:
    m = _REVISION_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else path.stem


def _changes_shape(text: str) -> bool:
    return any(op in text for op in SHAPE_CHANGING)


def _has_evidence(revision: str) -> bool:
    """存在以该 revision 命名的测试文件即视为有证据。"""
    if not TESTS.is_dir():
        return False
    stem = revision.strip()
    for p in TESTS.glob("test_*.py"):
        name = p.name
        if stem and (stem in name):
            return True
    return False


def _load_baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    try:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("exempt", []))


def _save_baseline(exempt: set[str]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps({"exempt": sorted(exempt)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def collect() -> dict:
    exempt = _load_baseline()
    shape_changing: list[dict] = []
    missing: list[dict] = []
    if VERSIONS.is_dir():
        for p in sorted(VERSIONS.glob("*.py")):
            if p.name.startswith("__"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if not _changes_shape(text):
                continue
            rev = _revision_of(p) or p.stem
            has_ev = _has_evidence(rev)
            row = {"revision": rev, "file": p.name, "evidence": has_ev, "exempt": rev in exempt}
            shape_changing.append(row)
            if not has_ev and rev not in exempt:
                missing.append(row)
    return {
        "shape_changing": shape_changing,
        "missing": missing,
        "exempt_count": len(exempt),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="迁移自证门禁")
    ap.add_argument("--json", action="store_true", help="输出纯 JSON")
    ap.add_argument("--update", action="store_true", help="把当前缺证据的迁移写入豁免清单")
    args = ap.parse_args(argv)

    data = collect()

    if args.update:
        exempt = _load_baseline()
        for row in data["missing"]:
            exempt.add(row["revision"])
        _save_baseline(exempt)
        print(f"[migration-evidence] 已写入 {len(data['missing'])} 条豁免 → {BASELINE.name}")
        return 0

    if args.json:
        print(json.dumps(data, ensure_ascii=False))
        return 1 if data["missing"] else 0

    print(
        f"[migration-evidence] 会改 schema 的迁移 {len(data['shape_changing'])} 个，"
        f"其中缺自证证据且未豁免 {len(data['missing'])} 个（豁免 {data['exempt_count']}）"
    )
    for row in data["missing"]:
        print(f"  ✗ {row['revision']}  ({row['file']}) —— 缺 tests/unit/test_*{row['revision']}*.py")
    if data["missing"]:
        print()
        print("修复方式：为每个迁移补一个测试，手工构造「旧库状态」再驱动迁移函数，")
        print("断言结构已按预期改变（参考 tests/unit/test_pii_col_width_r50.py）。")
        print("确认属历史遗留、暂不追溯的，登记进 migration_evidence.json 后重跑。")
        return 1
    print("[migration-evidence] OK：所有新增的 schema 变更迁移均自带自证证据")
    return 0


if __name__ == "__main__":
    sys.exit(main())