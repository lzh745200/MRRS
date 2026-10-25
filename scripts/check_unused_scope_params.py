#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""门禁：检测"作用域形参收下却从未使用"的函数（W18 P0-2 防复发）。

背景：dashboard._avg_per_capita_income(db, data_scope, ...) 收下了 data_scope
形参却一次没用，4 处调用点全在裸奔 —— 部门级管理员看到的是全库数据。这类缺陷
"看起来已隔离、实际没隔离"，人眼极难发现，且没有任何运行时告警。

本脚本用 AST 扫描 app/ 下所有函数：凡是参数名匹配作用域语义
（data_scope / org_scope / scope_filter）且函数体内完全未引用该名字的，
即判定为"收下不用"，退出码 1。

允许基线（BASELINE）：确属透传/占位的极小集合，新增必须说明理由。

用法：
    python scripts/check_unused_scope_params.py            # 检查（CI 门禁）
    python scripts/check_unused_scope_params.py --verbose  # 列出扫描统计
"""
import ast
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "backend", "app")

# 作用域形参的命名模式
SCOPE_PARAM_NAMES = {"data_scope", "org_scope", "scope_filter"}

# 允许的例外：{限定键: 理由}。新增必须写清"为什么必须透传但不用"。
BASELINE = {}


def _iter_py_files(base):
    for dirpath, _dirnames, filenames in os.walk(base):
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _load_names(func_node):
    """收集函数体内被引用的所有标识符（读用法）。"""
    used = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Name):
            used.add(node.id)
    return used


def scan_file(path):
    """返回 [(lineno, func_name, param)] 形式的违规列表。"""
    try:
        source = io.open(path, encoding="utf-8").read()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover - 仅防御被扫描文件本身损坏（语法错误/非 UTF-8），门禁不应因此中断
        print(f"[gate:unused_scope] 跳过无法解析的文件 {path}: {exc}", file=sys.stderr)
        return []

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
        scope_params = [a for a in args if a in SCOPE_PARAM_NAMES]
        if not scope_params:
            continue
        used = _load_names(node)
        for param in scope_params:
            if param not in used:
                violations.append((node.lineno, node.name, param))
    return violations


def main():
    verbose = "--verbose" in sys.argv
    all_found = []
    for path in _iter_py_files(APP_DIR):
        all_found.extend((path, *v) for v in scan_file(path))

    def rel(p):
        return os.path.relpath(p, ROOT).replace(os.sep, "/")

    new_found = []
    for path, lineno, func, param in all_found:
        key = f"{rel(path)}::{func}::{param}"
        if key in BASELINE:
            continue
        new_found.append((rel(path), lineno, func, param))

    if verbose:
        print(f"[gate:unused_scope] 扫描完成，命中 {len(all_found)} 项（基线 {len(BASELINE)}）")

    if new_found:
        print(f"[gate:unused_scope] FAIL: {len(new_found)} 处作用域形参收下未使用", file=sys.stderr)
        for path, lineno, func, param in new_found:
            print(f"  {path}:{lineno} {func}({param})", file=sys.stderr)
        print(
            "[gate:unused_scope] 修法：真正接线（过滤查询）或删除形参；"
            "确需透传请在 BASELINE 登记理由。",
            file=sys.stderr,
        )
        return 1

    print(f"[gate:unused_scope] OK: total={len(all_found)} baseline={len(BASELINE)} NEW=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
