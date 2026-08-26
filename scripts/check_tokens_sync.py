#!/usr/bin/env python
"""tokens 双维护一致性守卫（W11-043 · UI v2.0 P1 底座）。

校验 SCSS 桥接文件 tokens-vars.scss 中每一条 ``$var: var(--css-var)``
映射的 ``--css-var`` 确实在 tokens.scss 中有定义（任一主题块均可）。
漂移即非零退出 —— 防止「桥接引用了不存在的 token」这类静默失效。

用法:
    python scripts/check_tokens_sync.py            # 全量校验
    python scripts/check_tokens_sync.py --staged   # 仅当两文件有暂存改动时校验
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VARS_FILE = ROOT / "frontend" / "src" / "styles" / "tokens-vars.scss"
TOKENS_FILE = ROOT / "frontend" / "src" / "styles" / "tokens.scss"

_BRIDGE_RE = re.compile(r"^\$([\w-]+)\s*:\s*var\(--([\w-]+)\)", re.MULTILINE)
_DEFINE_RE = re.compile(r"^\s*--([\w-]+)\s*:", re.MULTILINE)


def _defined_css_vars() -> set[str]:
    text = TOKENS_FILE.read_text(encoding="utf-8")
    return {m.group(1) for m in _DEFINE_RE.finditer(text)}


def _bridge_mappings() -> list[tuple[str, str]]:
    text = VARS_FILE.read_text(encoding="utf-8")
    # 排除注释行内的示例
    lines = [
        line
        for line in text.splitlines()
        if not line.strip().startswith("//") and not line.strip().startswith("*")
    ]
    body = "\n".join(lines)
    return [(m.group(1), m.group(2)) for m in _BRIDGE_RE.finditer(body)]


def _has_staged_changes() -> bool:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=ROOT,
    ).stdout
    touched = {line.strip() for line in out.splitlines()}
    return str(VARS_FILE.relative_to(ROOT)) in touched or str(
        TOKENS_FILE.relative_to(ROOT)
    ) in touched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true",
                        help="仅当两个文件存在暂存改动时执行校验")
    args = parser.parse_args(argv)

    if args.staged and not _has_staged_changes():
        return 0

    defined = _defined_css_vars()
    broken = [
        (scss_var, css_var)
        for scss_var, css_var in _bridge_mappings()
        if css_var not in defined
    ]

    print(f"[tokens-sync] 桥接映射 {_bridge_mappings().__len__()} 条 / "
          f"tokens 定义 {len(defined)} 个 CSS 变量")

    if broken:
        print("TOKENS DRIFT —— 桥接引用了 tokens.scss 未定义的变量:")
        for scss_var, css_var in broken[:20]:
            print(f"  ${scss_var} -> --{css_var} (缺失)")
        if len(broken) > 20:
            print(f"  ... 及另外 {len(broken) - 20} 条")
        return 1

    print("[tokens-sync] 一致性 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
