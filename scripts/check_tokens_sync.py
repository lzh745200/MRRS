# -*- coding: utf-8 -*-
"""T043：tokens.scss 尾部 $ 映射与 tokens-vars.scss 一致性守卫（CI/pre-commit 可用）。

规则：
1. tokens-vars.scss 是权威源；其全部变量必须能在 tokens.scss 中找到同名映射（缺失即漂移）。
2. 同名变量的右侧值必须完全一致（防止双处手改漂移）。
3. tokens.scss 独有变量允许存在（历史遗留，仅提示）。
"""
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "styles"
TOKENS = ROOT / "tokens.scss"
VARS = ROOT / "tokens-vars.scss"

PAT = re.compile(r"^\$([\w-]+)\s*:\s*([^;]+);", re.M)


def extract(text: str) -> dict:
    return {k: v.strip() for k, v in PAT.findall(text)}


def main() -> int:
    a = extract(TOKENS.read_text(encoding="utf-8"))
    b = extract(VARS.read_text(encoding="utf-8"))
    errors = []
    for k, v in b.items():
        if k not in a:
            errors.append(f"[missing-in-tokens] ${k}")
        elif a[k] != v:
            errors.append(f"[value-drift] ${k}: tokens={a[k]!r} vs vars={v!r}")
    if errors:
        print("TOKENS DRIFT DETECTED:")
        for e in errors:
            print("  " + e)
        return 1
    print(f"[tokens-sync] OK ({len(b)} vars aligned, {len(a) - len(b)} legacy extras)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
