#!/usr/bin/env python3
"""校验文档中的量化描述与代码实际一致（文档漂移门禁）。

## 为什么需要

`CLAUDE.md` 里写死了大量易漂移的数字（端点数、路由模块数、测试用例数）。
实测发现它们全部滞后：文档 803 端点 / 实测 826；文档 13,942 后端用例 /
实测 13,987；文档 6,867 前端用例 / 实测 6,882。这类数字每次迭代都会漂，
靠人工维护必然失准，且会误导后来者与 CI 排查。

## 用法

    python scripts/check_doc_numbers.py            # 只校验（CI 门禁；不匹配则退出 1）
    python scripts/check_doc_numbers.py --update   # 自动把文档数字改为实测值
    python scripts/check_doc_numbers.py --full     # 额外校验需要跑 collect 的用例数

默认只校验**可快速获取**的指标（避免 CI 跑一次 collect 多花 30s）；
用例数这类需要 `pytest --collect-only` 的指标走 `--full`。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认 GBK，打印 "✓"/"✗" 会 UnicodeEncodeError 并使门禁假红；
# 门禁输出统一用 UTF-8（不支持 reconfigure 的旧解释器静默跳过）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - 仅旧解释器/特殊重定向
    pass

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DOC_FILE = ROOT / "CLAUDE.md"


# ── 实测值 ────────────────────────────────────────────────────────────────

def count_endpoints() -> int:
    """后端 /api 路由总数（加载 app 路由表，约 5-10s）。"""
    sys.path.insert(0, str(BACKEND))
    from app.main import app  # noqa: E402

    return sum(
        1
        for r in app.routes
        if hasattr(r, "methods") and getattr(r, "path", "").startswith("/api")
    )


def count_route_modules() -> tuple[int, int]:
    """(顶层路由模块数, 子包数)。只数真正含 @router 写路由定义的模块。"""
    api_root = BACKEND / "app" / "api" / "v1"
    top = 0
    for fp in api_root.glob("*.py"):
        if fp.name == "__init__.py":
            continue
        if "@router." in fp.read_text(encoding="utf-8", errors="replace"):
            top += 1
    subpkgs = sum(
        1
        for p in api_root.iterdir()
        if p.is_dir() and not p.name.startswith("_") and p.name != "__pycache__"
    )
    return top, subpkgs


def count_migrations() -> int:
    return len(list((BACKEND / "alembic" / "versions").glob("*.py")))


def count_frontend_test_files() -> int:
    return len(list((FRONTEND / "tests").rglob("*.test.ts")))


def count_backend_tests() -> int | None:
    """后端用例总数（需 collect，约 30s；失败返回 None 表示跳过）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=str(BACKEND), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode not in (0, 5):
        return None
    m = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout or "")
    return int(m.group(1)) if m else None


# ── 文档断言 ──────────────────────────────────────────────────────────────
# (名称, 正则（第 1 组为数字）, 实测函数, 是否 --full 才校验)
# 文档中的数字允许千分位逗号。
ASSERTIONS = [
    (
        "路由模块文件数",
        re.compile(r"(\d+) 个路由模块文件"),
        lambda: count_route_modules()[0],
        False,
    ),
    (
        "API 端点数",
        re.compile(r"[;；]\s*(\d[\d,]*) 个端点"),
        count_endpoints,
        False,
    ),
    (
        "前端测试文件数",
        re.compile(r"前端 (\d+) 文件"),
        count_frontend_test_files,
        False,
    ),
    (
        "后端测试用例数",
        re.compile(r"后端 ([\d,]+) 用例"),
        count_backend_tests,
        True,
    ),
]


def _to_int(text: str) -> int:
    return int(text.replace(",", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验文档量化描述与代码一致")
    parser.add_argument("--update", action="store_true", help="自动改写文档为实测值")
    parser.add_argument("--full", action="store_true", help="额外校验需 collect 的用例数")
    args = parser.parse_args()

    if not DOC_FILE.exists():
        print(f"找不到文档: {DOC_FILE}", file=sys.stderr)
        return 2

    content = DOC_FILE.read_text(encoding="utf-8")
    problems = []
    updated = content

    for name, pattern, measure, needs_full in ASSERTIONS:
        match = pattern.search(content)
        if not match:
            problems.append(f"  {name}: 文档中未找到可校验的描述（正则 {pattern.pattern}）")
            continue
        if needs_full and not args.full:
            print(f"[skip] {name}: 需 --full 才校验")
            continue
        try:
            actual = measure()
        except Exception as exc:  # pragma: no cover - 环境相关
            problems.append(f"  {name}: 实测失败（{type(exc).__name__}: {exc}）")
            continue
        if actual is None:
            print(f"[skip] {name}: 实测不可得")
            continue
        documented = _to_int(match.group(1))
        if documented == actual:
            print(f"[ok]   {name}: {actual}")
        else:
            problems.append(f"  {name}: 文档 {documented} / 实测 {actual}")
            if args.update:
                updated = pattern.sub(
                    lambda m, _a=actual: m.group(0).replace(
                        m.group(1), f"{_a:,}" if "," in m.group(1) else str(_a)
                    ),
                    updated,
                    count=1,
                )

    if args.update and updated != content:
        DOC_FILE.write_text(updated, encoding="utf-8")
        print(f"\n[update] 已改写 {DOC_FILE.name}")

    if problems:
        print("\n文档数字漂移：")
        for item in problems:
            print(item)
        if not args.update:
            print("\n修复：python scripts/check_doc_numbers.py --update（并把新增项补进 ASSERTIONS）")
        return 1

    print("\n文档数字一致性 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
