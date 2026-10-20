#!/usr/bin/env python
"""扫描 API 路由文件中的「裸 dict 返回」（违反 CONTEXT.md 不变量 3 envelope 契约）。

背景
----
本脚本旧实现用**单行正则** ``re.match(r'return\\s*\\{', line)``，只认
``return {`` 与花括号在同一行；跨行写法

    return {
        "code": 200,
        "success": True,
        ...
    }

虽经 5 行窗口兜底检查 envelope 关键字，但对「先换行、envelope 短语出现在 >5 行
之后」的形态仍会漏判 —— 实测审批模块有 19 处裸 dict 而本脚本报 **0**（门禁假绿）。
且该脚本**从未被任何 CI workflow 调用**（孤儿门禁）。

W25（2026-10-20）改造：
  * 改用 **AST** 判定：只看真正的 ``Return`` 节点，其 value 是否为 ``ast.Dict``；
  * 支持「三元/条件返回」「多行 dict」「嵌套容器」等所有形态；
  * ``return success_response(...)`` / ``ok_list(...)`` 等调用不告警；
  * **发现即退出码 1**（真门禁），``--max-bare N`` 可临时放宽（默认 0）；
  * ``--json`` 输出机器可读结果，便于 CI 注解。

用法
----
    python backend/scripts/scan_bare_returns.py            # CI 门禁（发现即非零退出）
    python backend/scripts/scan_bare_returns.py --list     # 仅列出，不施加门禁
    python backend/scripts/scan_bare_returns.py --json     # 机器可读
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import sys

_IGNORED_FILES = frozenset({"__init__.py"})

# 默认扫描根：``<repo>/backend/app/api/v1``。
# 注意：旧实现写成 ``os.path.join(os.path.dirname(__file__), "app", "api", "v1")``
# 即 ``backend/scripts/app/api/v1`` —— 该目录**根本不存在**，glob 返回空列表，
# 于是门禁恒报 0（这才是"审批模块 19 处裸 dict 却报 0"的真正原因；
# 正则单行匹配盲区是第二个独立缺陷）。
_DEFAULT_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "api", "v1"
)


def _iter_api_files(base: str):
    for path in sorted(glob.glob(os.path.join(base, "**", "*.py"), recursive=True)):
        if os.path.basename(path) in _IGNORED_FILES:
            continue
        yield path


def _is_bare_dict(value: ast.AST) -> bool:
    """value 是否为「裸 dict 字面量」返回。

    * ``ast.Dict`` → 是（唯一要收敛的形态）；
    * ``IfExp``（``a if c else b``）→ 两侧任一为裸 dict 即算；
    * ``BoolOp`` / ``Tuple`` / ``List`` → 递归检查元素；
    * ``Call`` / ``Name`` / ``Attribute`` → 否（走 envelope 工具或被转发）。
    """
    if isinstance(value, ast.Dict):
        return True
    if isinstance(value, ast.IfExp):
        return _is_bare_dict(value.body) or _is_bare_dict(value.orelse)
    if isinstance(value, (ast.BoolOp, ast.Tuple, ast.List)):
        elems = getattr(value, "values", None) or getattr(value, "elts", [])
        return any(_is_bare_dict(e) for e in elems)
    return False


def _dict_keys(value: ast.AST) -> list:
    """尽力取出字面量 dict 的字符串键（便于报告定位）。"""
    if not isinstance(value, ast.Dict):
        return []
    keys = []
    for key in value.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.append(key.value)
    return keys


class _BareDictReturnVisitor(ast.NodeVisitor):
    """收集「return {字面量 dict}」节点（含跨行与条件表达式）。"""

    def __init__(self, relpath: str):
        self.relpath = relpath
        self.findings = []

    def visit_Return(self, node: ast.Return):  # noqa: N802 - ast 回调命名
        value = node.value
        if value is not None and _is_bare_dict(value):
            self.findings.append(
                {
                    "file": self.relpath,
                    "line": node.lineno,
                    "col": node.col_offset + 1,
                    "keys": _dict_keys(value),
                }
            )
        self.generic_visit(node)


def scan(base: str) -> list:
    """扫描 *base* 目录，返回全部裸 dict 返回点。"""
    findings = []
    for path in _iter_api_files(base):
        rel = os.path.relpath(path, base)
        try:
            # utf-8-sig：容忍带 BOM 的源文件（否则整文件被跳过 → 门禁假绿）
            with open(path, "r", encoding="utf-8-sig") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=path)
        except (OSError, SyntaxError) as exc:  # pragma: no cover - 语法错误由 flake8 拦截
            print(f"[warn] 跳过无法解析的文件 {rel}: {exc}", file=sys.stderr)
            continue
        visitor = _BareDictReturnVisitor(rel)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="扫描 API 路由文件中的裸 dict 返回")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--list", action="store_true", help="仅列出，不施加退出码门禁")
    parser.add_argument(
        "--max-bare",
        type=int,
        default=0,
        help="全局允许上限（未启用基线时的绝对阈值，默认 0）",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="棘轮基线 JSON 路径（按文件计数，只允许持平或减少）",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="把当前扫描结果写入 --baseline 指定文件（只在收紧时使用）",
    )
    parser.add_argument(
        "--base",
        default=_DEFAULT_BASE,
        help="扫描根目录（默认 <repo>/backend/app/api/v1）",
    )
    args = parser.parse_args(argv)

    findings = scan(args.base)
    by_file = {}
    for item in findings:
        by_file[item["file"].replace("\\", "/")] = by_file.get(item["file"].replace("\\", "/"), 0) + 1

    if args.write_baseline:
        if not args.baseline:
            print("[error] --write-baseline 需要同时指定 --baseline", file=sys.stderr)
            return 2
        payload = {"total": len(findings), "by_file": dict(sorted(by_file.items()))}
        os.makedirs(os.path.dirname(os.path.abspath(args.baseline)), exist_ok=True)
        with open(args.baseline, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"[gate:bare_returns] 基线已写入 {args.baseline}（total={len(findings)}）")
        return 0

    if args.json:
        print(json.dumps({"total": len(findings), "by_file": by_file, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        print(f"Found {len(findings)} bare dict returns across {len(by_file)} files")
        if not args.baseline:
            for item in findings:
                keys = ",".join(item["keys"]) if item["keys"] else "?"
                print(f"  {item['file']}:{item['line']} ({item['col']}) keys=[{keys}]")

    if args.list:
        return 0

    # ── 棘轮模式：按文件对比基线，NEW 必须为 0 ──
    if args.baseline:
        if not os.path.exists(args.baseline):
            print(
                f"[gate:bare_returns] FAIL: 基线文件不存在 {args.baseline}"
                "\n首次启用请执行 --write-baseline 生成基线。",
                file=sys.stderr,
            )
            return 1
        with open(args.baseline, "r", encoding="utf-8") as fh:
            baseline = json.load(fh)
        base_map = baseline.get("by_file", {})
        new_violations = []
        for fname, count in sorted(by_file.items()):
            allowed = base_map.get(fname, 0)
            if count > allowed:
                new_violations.append((fname, count, allowed))
        regressions = [
            (fname, base_map.get(fname, 0), count)
            for fname, count in sorted(base_map.items())
            if by_file.get(fname, 0) > count
        ]
        if new_violations or regressions:
            for fname, count, allowed in new_violations:
                print(f"  [NEW] {fname}: {count} 处（基线 {allowed}）", file=sys.stderr)
            for fname, allowed, count in regressions:
                print(f"  [NEW] {fname}: {count} 处（基线 {allowed}）", file=sys.stderr)
            print(
                f"\n[gate:bare_returns] FAIL: NEW={len(new_violations) + len(regressions)}"
                f"（当前 {len(findings)} / 基线 {baseline.get('total', 0)}）"
                "\n裸 dict 返回只能减少不能新增；请改用 success_response()/ok_list()"
                "（CONTEXT.md 不变量 3）。",
                file=sys.stderr,
            )
            return 1
        print(
            f"[gate:bare_returns] OK: total={len(findings)} baseline={baseline.get('total', 0)} NEW=0"
        )
        return 0

    if len(findings) > args.max_bare:
        print(
            f"\n[gate:bare_returns] FAIL: {len(findings)} 处裸 dict 返回超过上限 {args.max_bare}。"
            "\n请改用 app.core.response 的 success_response() / ok_list()（CONTEXT.md 不变量 3）。",
            file=sys.stderr,
        )
        return 1
    print(f"\n[gate:bare_returns] OK: total={len(findings)} max={args.max_bare}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
