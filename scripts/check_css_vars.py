#!/usr/bin/env python3
"""check_css_vars.py — CSS 变量四横线笔误门禁（2026-08-29 事故回归防护）。

背景：tokens-vars.scss 注入约定曾系统性写成 var(----color-*)（四横线），
引用不存在的变量 → CSS 声明 invalid at computed-value time → 弹窗底色
透明退化为 initial（"登录已过期提示看不清"根因之一）。修复 142 处后
本脚本拦截 `var(----` 再发（含 .scss/.vue/.css 与 <style> 块）。

用法：
    python scripts/check_css_vars.py            # 扫描 frontend/src 全量
    python scripts/check_css_vars.py --staged   # 只扫 git 暂存文件（pre-commit 用）

退出码：0 通过；1 发现笔误。
"""
import argparse
import os
import re
import subprocess
import sys

PATTERN = re.compile(r"var\(----")
EXTS = {".scss", ".css", ".vue"}


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scan_file(path):
    try:
        text = open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    for i, line in enumerate(text.split("\n"), 1):
        if PATTERN.search(line):
            hits.append((i, line.strip()[:120]))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="只检查 git 暂存文件")
    args = ap.parse_args()

    root = _repo_root()
    if args.staged:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "-z"],
            capture_output=True, text=True, cwd=root,
        ).stdout
        files = [os.path.join(root, f) for f in out.split("\0") if f]
    else:
        files = []
        for base in ("frontend/src",):
            for dirpath, _dirs, names in os.walk(os.path.join(root, base)):
                for n in names:
                    files.append(os.path.join(dirpath, n))

    bad = 0
    for p in files:
        if os.path.splitext(p)[1].lower() not in EXTS or not os.path.isfile(p):
            continue
        for ln, snippet in _scan_file(p):
            rel = os.path.relpath(p, root)
            print(f"::error::四横线变量笔误 {rel}:{ln}: {snippet}")
            bad += 1

    if bad:
        print(f"[check_css_vars] FAIL：{bad} 处 var(---- 笔误（应为 var(--）")
        return 1
    print("[check_css_vars] OK：无四横线变量笔误")
    return 0


if __name__ == "__main__":
    sys.exit(main())
