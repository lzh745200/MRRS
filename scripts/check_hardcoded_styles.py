#!/usr/bin/env python
"""硬编码样式守卫（UI 精细化设计方案 v2.0 · P1 底座）

扫描 .vue 文件 <style> 块中的硬编码颜色（hex/rgb/rgba），
冻结存量（白名单豁免）、拦截增量 —— 先冻结再消化，最终清零。

用法:
    python scripts/check_hardcoded_styles.py                # 全量报告（退出码 0）
    python scripts/check_hardcoded_styles.py --staged       # 仅暂存文件（pre-commit 用）
    python scripts/check_hardcoded_styles.py --files a.vue b.vue

退出码语义:
    - 新增违规（不在 baseline 中）→ 非零（拦截提交）
    - 仅有存量违规 → 零（放行，打印消化进度）

Baseline: scripts/hardcoded_styles_baseline.json（存量豁免清单，
由 --update-baseline 生成；只允许缩小不允许扩大——脚本强制校验）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "hardcoded_styles_baseline.json"

# hex(3/4/6/8 位) 与 rgb()/rgba() 字面量
_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_RGB_RE = re.compile(r"\brgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+(?:\s*,\s*[\d.]+)?\s*\)")

# 明确豁免：非样式语境的误报
_LINE_WHITELIST = [
    "url(data:",          # data URI 内嵌资源
    "data:image",         # 同上
    "// #",               # 注释里的色值说明
    "/* #",               # 块注释
]

STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)


def _extract_violations(text: str) -> list[str]:
    """提取 <style> 块内的硬编码颜色字面量（带行内容用于定位）。"""
    found: list[str] = []
    for block in STYLE_BLOCK_RE.finditer(text):
        body = block.group(1)
        for line in body.splitlines():
            if any(w in line for w in _LINE_WHITELIST):
                continue
            for m in _HEX_RE.finditer(line):
                found.append(m.group(0).lower())
            for m in _RGB_RE.finditer(line):
                found.append(m.group(0))
    return found


def _violation_key(filepath: str, color: str, index: int) -> str:
    """同一文件同一颜色的多次出现按序号区分。"""
    return f"{filepath}::{color}::{index}"


def _collect(files: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for f in files:
        p = ROOT / f
        if not p.exists() or p.suffix != ".vue":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        vols = _extract_violations(text)
        if vols:
            result[f.replace("\\", "/")] = vols
    return result


def _git_staged_vue_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, cwd=ROOT,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip().endswith(".vue")]


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="仅检查 git 暂存的 .vue")
    group.add_argument("--files", nargs="*", help="显式文件列表")
    parser.add_argument("--update-baseline", action="store_true",
                        help="重新生成存量基线（仅缩小允许，扩大需人工确认）")
    args = parser.parse_args(argv)

    if args.update_baseline:
        all_vue = [
            str(p.relative_to(ROOT)).replace("\\", "/")
            for p in (ROOT / "frontend" / "src").rglob("*.vue")
        ]
        current = _collect(all_vue)
        old = _load_baseline()
        # 只许缩小：新基线若出现旧基线没有的文件/数量增长则拒绝
        growth = []
        for fp, colors in current.items():
            old_n = len(old.get(fp, []))
            if len(colors) > old_n:
                growth.append(f"{fp}: {old_n} -> {len(colors)}")
        if growth and old:
            print("BASELINE REJECTED — 存在数量增长（应修代码而非扩基线）:")
            for g in growth[:10]:
                print(f"  {g}")
            return 2
        BASELINE_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        total = sum(len(v) for v in current.values())
        print(f"baseline updated: {total} violations in {len(current)} files")
        return 0

    if args.staged:
        files = _git_staged_vue_files()
        if not files:
            return 0
    elif args.files:
        files = args.files
    else:
        files = [
            str(p.relative_to(ROOT)).replace("\\", "/")
            for p in (ROOT / "frontend" / "src").rglob("*.vue")
        ]

    current = _collect(files)
    baseline = _load_baseline()

    new_violations: list[str] = []
    remaining_total = 0
    for fp, colors in sorted(current.items()):
        allowed = baseline.get(fp, [])
        # 按颜色分组计数对比：同色出现次数不得超过基线
        from collections import Counter

        cur_cnt, base_cnt = Counter(colors), Counter(allowed)
        for color, n in cur_cnt.items():
            remaining_total += n
            if n > base_cnt.get(color, 0):
                new_violations.append(f"{fp}: {color} x{n} (baseline {base_cnt.get(color, 0)})")

    total_now = sum(len(v) for v in current.values())
    print(f"[hardcoded-styles] 当前 {total_now} 处 / 基线 {sum(len(v) for v in baseline.values())} 处")

    if new_violations:
        print("HARDCODED COLOR — 新增硬编码颜色被拦截（请改用 var(--token)）:")
        for v in new_violations[:20]:
            print(f"  {v}")
        if len(new_violations) > 20:
            print(f"  ... 及另外 {len(new_violations) - 20} 处")
        return 1

    if total_now < sum(len(v) for v in baseline.values()):
        print("[hardcoded-styles] 存量减少 ✓ 可运行 --update-baseline 收紧基线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
