#!/usr/bin/env python3
"""常量与测试/文档字面量一致性门禁（防"常量改了、测试没改"）。

## 为什么需要

2026-10-25 的真实失败：`MAX_PAGE_SIZE` 由 100 调整为 200（分页硬上限收口），
但 `tests/unit/test_svc_batch.py::test_h10` 仍断言 `MAX_PAGE_SIZE == 100`。
本地只跑了相关套件、CI 的 seg10 才跑到它 → PR Checks 红 → 发布门禁拒绝出包。
这类"常量单一值 + 测试写死字面量"的漂移完全可以在**提交前**机械检测。

## 检查口径

1. 解析 `backend/app/core/constants.py` 的顶层常量（int / float / str / bool）；
2. 扫描 `backend/tests/`、`frontend/src/`、`docs/` 中形如 `NAME == <字面量>` /
   `NAME = <字面量>` 的断言；
3. 若常量可解析且与字面量不一致 → 报错（fail-closed：拿不到常量值时跳过该常量）。

限制：只做**词法级**比对，不执行代码；`NAME == other`、变量比较等一律跳过。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parent.parent

# Windows 控制台默认 GBK，打印非 ASCII 会 UnicodeEncodeError 并让门禁"假红"；
# 与 scripts/check_doc_numbers.py 同款处理。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - 旧解释器/特殊重定向
    pass
CONSTANTS = ROOT / "backend" / "app" / "core" / "constants.py"
# 只扫描后端测试：
# - frontend/src 有自己的同名前端口径（如 DEFAULT_PAGE_SIZE=12），与后端 constants.py
#   不是同一命名空间，纳入会产生假阳性；
# - docs 会引用历史值做说明（如"曾断言 100"），也会假阳性；
# - 本门禁自身的测试文件用字面量构造"漂移样例"，必须排除。
SCAN_DIRS = [
    ROOT / "backend" / "tests",
]
SKIP_FILES = {"backend/tests/unit/test_check_constants_sync.py"}
SKIP_PARTS = {"node_modules", "coverage", ".git", "__pycache__"}

ASSERT_RE = re.compile(
    r"\b([A-Z][A-Z0-9_]{2,})\s*={1,3}\s*"
    r"(-?\d+(?:\.\d+)?|\"[^\"]*\"|'[^']*'|True|False)(?![A-Za-z0-9_])"
)


def parse_constants(path: Path = CONSTANTS) -> Dict[str, Any]:
    """解析 constants.py 顶层赋值（仅字面量），无法解析的常量忽略。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: Dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        name = target.id
        if not name.isupper():
            continue
        try:
            values[name] = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
    return values


def _literal(value: str) -> Any:
    if value in ("True", "False"):
        return value == "True"
    if value.startswith(("'", '"')):
        return value[1:-1]
    return float(value) if "." in value else int(value)


def iter_scan_files(dirs: Iterable[Path]) -> Iterable[Path]:
    for root in dirs:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".vue", ".md", ".js"}:
                continue
            if SKIP_PARTS & set(path.parts):
                continue
            try:
                rel = path.relative_to(ROOT).as_posix()
            except ValueError:
                rel = path.as_posix()
            if rel in SKIP_FILES:
                continue
            yield path


def check(constants: Dict[str, Any], dirs: List[Path]) -> List[str]:
    problems: List[str] = []
    for path in iter_scan_files(dirs):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in ASSERT_RE.finditer(text):
            name, raw = match.group(1), match.group(2)
            if name not in constants:
                continue
            expected = constants[name]
            actual = _literal(raw)
            if actual != expected:
                rel = path.relative_to(ROOT).as_posix()
                line_no = text[: match.start()].count("\n") + 1
                problems.append(
                    f"{rel}:{line_no}: {name} 断言为 {raw}，但 constants.py 里是 {expected!r}"
                )
    return problems


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="常量↔字面量一致性门禁")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--dirs", nargs="*", default=None, help="覆盖扫描目录（测试用）")
    args = parser.parse_args(argv)

    constants = parse_constants()
    dirs = [Path(d) for d in args.dirs] if args.dirs else SCAN_DIRS
    problems = check(constants, dirs)

    if args.json:
        import json as _json

        print(_json.dumps({"constants": len(constants), "problems": problems}, ensure_ascii=False))
    elif problems:
        print(f"[constants-sync] {len(problems)} 处常量断言漂移：")
        for p in problems:
            print(f"  ✗ {p}")
        print("  修复：按 constants.py 的当前值更新断言（常量变更时请同提交更新引用）")
    else:
        print(f"[constants-sync] OK（{len(constants)} 个常量，0 处漂移）")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
