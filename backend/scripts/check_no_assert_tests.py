#!/usr/bin/env python
"""零断言测试棘轮门禁（W27 P1）—— 防"空壳测试"重新长出来。

## 为什么需要

W26 全栈检测发现 `tests/test_approval_idempotency.py` 的 **10 个测试函数体全是 `pass`**：
不建数据、不调被测代码、不写任何断言。它们让"审批幂等"这一关键属性**看起来有覆盖**，
实际零验证 —— 而在重写这些用例的当轮，立刻挖出「重复提交会产生 2 条待审批任务」
的真实缺陷（`submit_approval` 无幂等判定）。

空壳测试比没有测试更糟：它制造虚假安全感，且会随覆盖率统计一起"变绿"。

## 判定口径

测试函数（`def test*` / `async def test*`）必须至少满足其一：
1. 有 `assert` 语句；
2. 调用了 mock 断言（`assert_called*` 等以 `assert` 开头的属性/函数）；
3. 使用了 `pytest.raises` / `warns` / `deprecated_call` / `fail`（含 with 形式）；
4. 显式标记豁免：函数上带 `@pytest.mark.no_assert`（用于"仅验证不抛异常"的
   合理 smoke 用例，必须写明理由）。

## 棘轮

基线记录在 ``scripts/gate_baselines/no_assert_tests_baseline.json``，
**只允许持平或减少**：新增零断言测试即 NEW>0 → 退出码 1。

    python scripts/check_no_assert_tests.py                 # 门禁
    python scripts/check_no_assert_tests.py --list          # 打印全部违规
    python scripts/check_no_assert_tests.py --write-baseline # 重写基线（需评审）
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = BACKEND_ROOT / "tests"
BASELINE_PATH = (
    BACKEND_ROOT / "scripts" / "gate_baselines" / "no_assert_tests_baseline.json"
)

ASSERTION_CALLS = {
    "raises", "warns", "deprecated_call", "fail", "xfail", "skip",
}
EXEMPT_MARKER = "no_assert"


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""


def _has_assertion(fn: ast.AST) -> bool:
    for n in ast.walk(fn):
        if isinstance(n, ast.Assert):
            return True
        if isinstance(n, ast.Call):
            name = _call_name(n)
            # mock 断言族：assert_called / assert_called_once_with / assert_not_called ...
            if name.startswith("assert") or name in ASSERTION_CALLS:
                return True
        if isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and _call_name(ctx) in ASSERTION_CALLS:
                    return True
    return False


def _is_exempt(fn: ast.AST) -> bool:
    """是否标记 `@pytest.mark.no_assert`（附带理由写在注释里，供人工评审）。"""
    for dec in getattr(fn, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == EXEMPT_MARKER:
            return True
        if isinstance(target, ast.Name) and target.id == EXEMPT_MARKER:
            return True
    return False


def collect_violations() -> list[str]:
    """返回形如 ``tests/unit/foo.py::TestA::test_x`` 的唯一标识。

    必须带**类路径**：同一文件里多个测试类可以有同名方法
    （实测 `test_backup_scheduler_jobs.py` 有 4 个 `test_exception_is_logged`），
    只用 `文件::方法名` 会产生重复条目，让基线与实际计数对不上。
    """
    found: list[str] = []
    unparsable: list[str] = []

    def _walk(body, prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                _walk(node.body, f"{prefix}{node.name}::")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("test"):
                    continue
                if _has_assertion(node) or _is_exempt(node):
                    continue
                found.append(f"{prefix}{node.name}")

    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        try:
            # 必须 utf-8-sig：Windows 下 PowerShell `Set-Content -Encoding UTF8`、
            # 记事本等会写 BOM，utf-8 读取会让 ast.parse 抛
            # "invalid non-printable character U+FEFF"，从而被静默跳过
            # —— 那等于给门禁开了个后门（实测 BOM 文件确实没被发现）。
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            # **不静默跳过**：无法解析的测试文件对门禁是不可见的，
            # 必须当作硬失败上报，否则"加个 BOM 就绕过门禁"。
            unparsable.append(f"{rel}  ({type(exc).__name__}: {exc})")
            continue
        _walk(tree.body, f"{rel}::")

    if unparsable:
        raise RuntimeError(
            "[gate:no_assert_tests] 以下测试文件无法解析，门禁无法覆盖：\n  "
            + "\n  ".join(unparsable)
        )
    return found


def _load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return set(data.get("entries", []))


def _write_baseline(entries: list[str]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "W27 零断言测试棘轮基线。只允许持平或减少；"
            "新增零断言测试会让门禁失败。修复方式：补真实断言，"
            "或对'仅验证不抛异常'的合理 smoke 用例加 @pytest.mark.no_assert。"
        ),
        "count": len(entries),
        "entries": sorted(entries),
    }
    BASELINE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    violations = collect_violations()
    current = set(violations)

    if "--list" in argv:
        print(f"[gate:no_assert_tests] 当前 {len(current)} 个零断言测试函数：")
        for v in sorted(current):
            print("  ", v)
        return 0

    if "--write-baseline" in argv:
        _write_baseline(violations)
        print(f"[gate:no_assert_tests] 基线已写入 {BASELINE_PATH}（{len(violations)} 条）")
        return 0

    baseline = _load_baseline()
    new = sorted(current - baseline)
    fixed = sorted(baseline - current)

    print(
        f"[gate:no_assert_tests] total={len(current)} baseline={len(baseline)} "
        f"NEW={len(new)} FIXED={len(fixed)}"
    )
    if new:
        print("新增零断言测试（必须补断言或加 @pytest.mark.no_assert）：")
        for item in new[:40]:
            print(f"  x {item}")
        if len(new) > 40:
            print(f"  ... 共 {len(new)} 条")
        return 1
    if fixed:
        print(
            f"提示：有 {len(fixed)} 条已修复，可执行 "
            "`python scripts/check_no_assert_tests.py --write-baseline` 收紧基线"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
