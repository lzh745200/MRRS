#!/usr/bin/env python3
"""从 backend/app/api/v1 的路由源码提取全部 HTTP 端点清单, 生成 Markdown 骨架。

用途: 《API接口文档》的端点清单由本脚本生成, 保证与代码 100% 同步;
接口变更后重跑即可刷新清单(文档中的业务说明需人工维护)。

用法:
    python scripts/docs/extract_api_endpoints.py            # 输出到 stdout
    python scripts/docs/extract_api_endpoints.py -o out.md  # 输出到文件
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "backend" / "app" / "api" / "v1"

METHODS = {"get", "post", "put", "delete", "patch"}


def _literal_str(node: ast.AST) -> str | None:
    """尽力把 AST 节点求值为字符串(支持常量与简单 f-string/join), 失败返回 None。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f-string
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                parts.append("{}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal_str(node.left), _literal_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _decorator_method_path(dec: ast.AST) -> tuple[str, str] | None:
    """从 @router.get("/path") 装饰器提取 (METHOD, path)。"""
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    method = dec.func.attr.lower()
    if method not in METHODS:
        return None
    path = ""
    if dec.args:
        first = _literal_str(dec.args[0])
        if first is not None:
            path = first
    return method.upper(), path


def _func_summary(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    doc = ast.get_docstring(fn) or ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    return first


def _auth_hint(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """启发式: 依据参数默认值/函数体出现的依赖判断鉴权要求。"""
    src = ast.unparse(fn)
    hints = []
    if "require_admin" in src:
        hints.append("管理员")
    if "Depends(get_current_user)" in src or "get_current_active_user" in src:
        hints.append("登录")
    if "_client_is_loopback" in src:
        hints.append("仅本机")
    if "verify_pass_code" in src or "verification_code" in src:
        hints.append("含校验码")
    return "/".join(hints) if hints else "登录/公开"


def parse_module(path: Path) -> dict | None:
    tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
    prefix, tags = "", []
    endpoints: list[dict] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "APIRouter":
                for kw in call.keywords:
                    if kw.arg == "prefix":
                        prefix = _literal_str(kw.value) or ""
                    elif kw.arg == "tags" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        tags = [s for s in (_literal_str(e) for e in kw.value.elts) if s]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                mp = _decorator_method_path(dec)
                if mp:
                    method, sub = mp
                    endpoints.append({
                        "method": method,
                        "path": f"{prefix}{sub}" or "/",
                        "summary": _func_summary(node),
                        "auth": _auth_hint(node),
                        "name": node.name,
                    })
    if not endpoints:
        return None
    return {"file": path.name, "prefix": prefix, "tags": tags, "endpoints": endpoints}


def collect() -> list[dict]:
    results = []
    files = sorted(API_DIR.rglob("*.py"))
    for f in files:
        if f.name == "__init__.py":
            continue
        try:
            mod = parse_module(f)
        except SyntaxError as e:
            print(f"[WARN] 解析失败 {f}: {e}", file=__import__("sys").stderr)
            continue
        if mod:
            # system/ 子包有父 router(prefix="/system")二层挂载, 完整路径需拼接;
            # auth/data/import_export/monitoring 子包无父前缀, 不处理
            rel = f.relative_to(API_DIR)
            if rel.parts[0] == "system":
                mod["prefix"] = f"/system{mod['prefix']}"
                for e in mod["endpoints"]:
                    if not e["path"].startswith("/system"):
                        e["path"] = f"/system{e['path']}"
            results.append(mod)
    return results


def render(mods: list[dict]) -> str:
    lines = []
    total = sum(len(m["endpoints"]) for m in mods)
    lines.append(f"<!-- 由 scripts/docs/extract_api_endpoints.py 自动生成, 共 {len(mods)} 个模块 / {total} 个端点。")
    lines.append("     业务说明为人工维护部分; 重新生成仅覆盖端点清单, 勿整文件覆盖。 -->")
    lines.append("")
    for m in mods:
        tag = m["tags"][0] if m["tags"] else ""
        lines.append(f"### {m['file']} — {tag} `{m['prefix']}`")
        lines.append("")
        lines.append("| 方法 | 路径 | 说明 | 鉴权 |")
        lines.append("|------|------|------|------|")
        for e in m["endpoints"]:
            summary = e["summary"].replace("|", "/") or e["name"]
            lines.append(f"| {e['method']} | `{e['path']}` | {summary} | {e['auth']} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", help="输出文件路径(默认 stdout)")
    args = ap.parse_args()
    text = render(collect())
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"written: {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
