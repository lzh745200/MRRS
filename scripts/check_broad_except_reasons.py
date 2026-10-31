#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""宽泛异常捕获理由门禁（2026-10-31 巡检新增）。

## 背景

项目已有 check_pragma_reasons.py 管住 "pragma: no cover"（覆盖率豁免必须写理由），
但没有管住 "noqa: BLE001"（宽泛捕获 except Exception）—— 同一类「豁免必须留痕」的
规则只覆盖了一半，形成门禁盲区。

巡检实测：backend/app 有 88 处 noqa: BLE001，其中 15 处没有理由。逐处核验后确认这
15 处都是设计意图（体检/预检单项失败降级为 error_type 返回，不中断整轮；备份探测
失败降级为保守值并 warning），只是缺理由注释 —— 已全部补齐。

## 口径

noqa: BLE001 之后必须同行给出理由：- / — / : / ： 后跟至少 2 个非空字符，或紧跟 # 注释。

## 为什么零容忍

理由已全部补齐（当前 0 处违规），故直接要求零违规而非棘轮：新增宽泛捕获必须当场
写清「为什么不能收窄到具体异常类型」。

用法：

    python scripts/check_broad_except_reasons.py
    ... --all / --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "backend" / "app"]

_BLE = re.compile(r"noqa:\s*BLE001(?P<tail>.*)$")
_REASON = re.compile(r"^[—:\-：]\s*\S{2,}")


def has_reason(line: str) -> bool:
    """同行是否带理由（没写 BLE001 的行一律视为合规）。"""
    m = _BLE.search(line)
    if not m:
        return True
    tail = m.group("tail").strip().lstrip("#").strip()
    if not tail:
        return False
    if tail.startswith("pragma"):
        return bool(re.search(r"[—:\-：]\s*\S{2,}", tail))
    return bool(_REASON.match(tail))


def find_violations() -> list:
    out = []
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.py")):
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if "BLE001" in line and not has_reason(line):
                    rel = str(f.relative_to(ROOT)).replace("\\", "/")
                    out.append({"file": rel, "line": i, "code": line.strip()})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="宽泛异常捕获理由门禁")
    ap.add_argument("--all", action="store_true", help="列出全部违规")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    bad = find_violations()
    if args.json:
        print(json.dumps({"violations": len(bad), "items": bad}, ensure_ascii=False))
        return 1 if bad else 0

    if not bad:
        print("[broad-except] OK：所有 noqa: BLE001 均已注明理由")
        return 0

    print("[broad-except] %d 处宽泛捕获没有理由：" % len(bad))
    for item in bad:
        print("  %s:%d  %s" % (item["file"], item["line"], item["code"][:100]))
    print()
    print("修复：同行补理由，例如 # noqa: BLE001 - 体检单项失败降级为 error_type，不中断整轮")
    print("      理由必须说明「为什么不能收窄到具体异常类型」。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
