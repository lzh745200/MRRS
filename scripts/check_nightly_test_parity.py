#!/usr/bin/env python3
"""Nightly 与 PR Checks 的测试覆盖面一致性门禁（防"PR 绿、Nightly 红"）。

## 为什么需要

2026-10-25 Nightly 连续红：`app/api/v1/permission_packs.py` 覆盖率仅 38.04%，
`app/services/approval_workflow_service.py` 缺 1 行。根因是两套 **不同的测试分组**：

- PR Checks：`scripts/run_backend_tests_segmented.py` 12 段，其中 `seg11-tests-root`
  覆盖 `backend/tests/*.py` 根目录测试；
- Nightly：`.github/workflows/nightly-full.yml` 自己的 6 段，只列了
  `tests/integration`、`tests/security`、`tests/unit/**`，**漏了 `tests/*.py` 根目录**。
  `backend/tests/test_permission_packs.py` 恰好在那，于是 nightly 永远不跑它 →
  app 覆盖率 99.82% < 100 → Nightly 红，而 PR Checks 全绿。

本门禁把"Nightly 是否覆盖 backend/tests 下所有测试文件"变成机械检查：
解析 nightly 工作流里 `ci_backend_test_segment.sh` 的路径参数（含 glob），
展开后与 `backend/tests` 实际文件集合求差；有遗漏即 fail-closed。
"""

from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "nightly-full.yml"
TESTS = ROOT / "backend" / "tests"

# 只统计测试文件；忽略缓存与辅助模块
TEST_FILE_GLOBS = ("test_*.py", "*_test.py")
IGNORE_PARTS = {"__pycache__", ".pytest_cache"}

CMD_RE = re.compile(r"ci_backend_test_segment\.sh[^\n]*")
TOKEN_RE = re.compile(r"(tests/[^\s\"']*)")


def _expand(patterns: list[str]) -> set[str]:
    """把 nightly 里的 tests/... 参数（可含 glob）展开为相对 backend 的路径集合。"""
    matched: set[str] = set()
    for pattern in patterns:
        pattern = pattern.strip().rstrip("\\")
        if not pattern.startswith("tests/"):
            continue
        for path in TESTS.rglob("*"):
            if not path.is_file() or not path.name.startswith("test_"):
                continue
            if IGNORE_PARTS & set(path.parts):
                continue
            rel = path.relative_to(TESTS.parent).as_posix()
            # 目录参数（无通配符）按前缀覆盖其下所有测试；含通配符按 glob 匹配
            if any(ch in pattern for ch in "*?["):
                hit = fnmatch.fnmatch(rel, pattern)
            else:
                hit = rel == pattern or rel.startswith(pattern.rstrip("/") + "/")
            if hit:
                matched.add(rel)
    return matched


def all_test_files() -> set[str]:
    files: set[str] = set()
    for path in TESTS.rglob("*.py"):
        if not path.is_file() or IGNORE_PARTS & set(path.parts):
            continue
        if any(fnmatch.fnmatch(path.name, g) for g in TEST_FILE_GLOBS):
            files.add(path.relative_to(TESTS.parent).as_posix())
    return files


def nightly_patterns(workflow: Path = WORKFLOW) -> list[str]:
    text = workflow.read_text(encoding="utf-8")
    patterns: list[str] = []
    for cmd in CMD_RE.findall(text):
        patterns.extend(TOKEN_RE.findall(cmd))
    return sorted(set(patterns))


def missing_tests(workflow: Path = WORKFLOW) -> tuple[list[str], list[str]]:
    patterns = nightly_patterns(workflow)
    covered = _expand(patterns)
    missing = sorted(all_test_files() - covered)
    return patterns, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nightly 测试覆盖与 backend/tests 的一致性门禁")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    patterns, missing = missing_tests()
    if args.json:
        import json as _json

        print(_json.dumps({"patterns": patterns, "missing": missing}, ensure_ascii=False))
    elif missing:
        print(f"[nightly-parity] Nightly 未覆盖 {len(missing)} 个测试文件（PR Checks 会跑、Nightly 不会）：")
        for rel in missing:
            print(f"  [MISSING] {rel}")
        print("  修复：把对应目录/glob 加进 nightly-full.yml 的 ci_backend_test_segment.sh 参数")
    else:
        print(f"[nightly-parity] OK：Nightly 覆盖 backend/tests 全部 {len(all_test_files())} 个测试文件")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
