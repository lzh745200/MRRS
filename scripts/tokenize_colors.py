"""B1 批次：硬编码颜色 → 设计令牌 机械替换（UI v2.0 · P4）。

范围：frontend/src/**/*.vue 的 <style> 块内（与守卫脚本同口径）。
映射表取自 docs/design/hardcoded-colors-report.md 频次 Top15 中
语义无歧义的子集（#fff/#ffffff 文字反白场景、阴影 rgba、需新 token
决策的 #003366 留给人工批次）。

规则：
- 词边界匹配（#666 不误伤 #666666/#666ccc）
- 跳过 url(data:...) 与注释行（与守卫白名单一致）
- 仅 <style lang="scss"> 块应用 $military-dark（纯 CSS 块跳过该条）

用法:
    python scripts/tokenize_colors.py            # 执行替换并输出统计
    python scripts/tokenize_colors.py --dry-run  # 只统计不写入
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"

STYLE_BLOCK_RE = re.compile(
    r"(<style\b[^>]*>)(.*?)(</style>)", re.DOTALL | re.IGNORECASE
)

LINE_WHITELIST = ("url(data:", "data:image", "// #", "/* #")

# 无歧义映射：字面量(小写) → 替代物
CSS_VAR_MAP = {
    "#303133": "var(--color-text-primary)",
    "#606266": "var(--color-text-regular)",
    "#666": "var(--color-text-secondary)",
    "#f5f7fa": "var(--color-bg-hover)",
    "#f0f0f0": "var(--color-bg-hover)",
    "#e4e7ed": "var(--color-border-light)",
    "#ebeef5": "var(--color-border-light)",
    "#2d6a4f": "var(--color-primary)",
    "#40916c": "var(--color-primary-light-1)",
}
# 仅 scss 块可用的 SCSS 变量映射
SCSS_ONLY_MAP = {
    "#1b4332": "$military-dark",
}

# 预编译词边界正则：hex 后不能跟 [0-9a-fA-F]
def _hex_re(literal: str) -> re.Pattern:
    return re.compile(re.escape(literal) + r"(?![0-9a-fA-F])", re.IGNORECASE)


CSS_RES = {lit: _hex_re(lit) for lit in CSS_VAR_MAP}
SCSS_RES = {lit: _hex_re(lit) for lit in SCSS_ONLY_MAP}


def tokenize_style_body(body: str, is_scss: bool) -> tuple[str, Counter]:
    stats: Counter = Counter()
    out_lines: list[str] = []
    for line in body.splitlines(keepends=True):
        if any(w in line for w in LINE_WHITELIST):
            out_lines.append(line)
            continue
        newline = line.endswith("\n")
        core = line[:-1] if newline else line

        for lit, rx in CSS_RES.items():
            core, n = rx.subn(CSS_VAR_MAP[lit], core)
            if n:
                stats[lit] += n
        if is_scss:
            for lit, rx in SCSS_RES.items():
                core, n = rx.subn(SCSS_ONLY_MAP[lit], core)
                if n:
                    stats[lit] += n

        out_lines.append(core + ("\n" if newline else ""))
    return "".join(out_lines), stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    total: Counter = Counter()
    touched_files = 0

    for vue in sorted(SRC.rglob("*.vue")):
        try:
            text = vue.read_text(encoding="utf-8")
        except OSError:
            continue
        if "<style" not in text:
            continue

        changed = False

        def _repl(m: re.Match) -> str:
            nonlocal changed
            open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
            is_scss = "scss" in open_tag.lower()
            new_body, stats = tokenize_style_body(body, is_scss)
            if stats:
                changed = True
                total.update(stats)
                for lit, n in stats.items():
                    print(f"{vue.relative_to(ROOT)}:{lit} x{n}")
            return f"{open_tag}{new_body}{close_tag}"

        new_text = STYLE_BLOCK_RE.sub(_repl, text)
        if changed:
            touched_files += 1
            if not args.dry_run:
                vue.write_text(new_text, encoding="utf-8")

    print(f"\n== {'DRY-RUN' if args.dry_run else 'APPLIED'}: "
          f"{sum(total.values())} replacements in {touched_files} files ==")
    for lit, n in total.most_common():
        repl = CSS_VAR_MAP.get(lit) or SCSS_ONLY_MAP.get(lit)
        print(f"  {lit} -> {repl}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
