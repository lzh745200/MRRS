"""无界读取棘轮门禁（P-1 · 遗留风险治理计划 2026-09-13）。

拦截 backend/app/** 中两类"先整包入内存再校验"的写法（AST 判定，注释/文档串
不会误报）：

1. ZIP 成员裸读：zf.read(...) / zipf.read(...)（未经 read_zip_member 预检）；
2. 整体文件读：await x.read()（**无长度参数**；带长度参数的分块读放行）。

为什么（R2 根因）：xlsx/zip 是高压缩比容器，容器体积合规 ≠ 解压后合规
（1MB deflate 可膨胀到数十 GB）；UploadFile 背后是 SpooledTemporaryFile，
await file.read() 会把整包物化进内存后才比较长度 —— 校验只能拒绝请求，
挡不住内存峰值（单机离线部署下单请求即可 OOM，整库应用不可用）。

合法写法（本门禁放行）：read_zip_member / ensure_zip_within_limit /
read_upload_with_limit / save_upload_file / shutil.copyfileobj / 带长度参数的
分块读（await f.read(1MB)）。

豁免：同一行写 nosec:unbounded-read <理由>；历史合法点写进基线
（backend/scripts/gate_baselines/unbounded_read.txt，支持 # 注释行）。

用法::

    python backend/scripts/check_unbounded_read.py
    python backend/scripts/check_unbounded_read.py --baseline
"""

import ast
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "unbounded_read"
ZIP_VARS = {"zf", "zipf", "package_zip", "src_zip"}
GUARD_MARKERS = (
    "read_zip_member(",
    "ensure_zip_within_limit(",
    "read_upload_with_limit(",
    "save_upload_file(",
    "copyfileobj(",
)


def _enclosing_functions(tree):
    """返回 {子节点 id: 所属函数节点} 映射。"""
    owners = {}
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(func):
                owners[id(child)] = func
    return owners


def scan_text(rel_path: str, text: str) -> list:
    lines = text.splitlines()
    hits = []
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover
        return hits

    owners = _enclosing_functions(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            call = node.value
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "read"
                and not call.args
            ):
                hits.append(_format(rel_path, text, lines, owners, node, "整体读 await x.read()（无长度参数）"))
            continue
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "read"):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id in ZIP_VARS):
            continue
        hits.append(_format(rel_path, text, lines, owners, node, "ZIP 成员裸读 zf.read()（未经预检）"))
    return [h for h in hits if h]


def _format(rel_path, text, lines, owners, node, reason):
    line = lines[node.lineno - 1] if node.lineno - 1 < len(lines) else ""
    if "nosec:unbounded-read" in line:
        return None
    owner = owners.get(id(node))
    if owner is not None:
        body = ast.get_source_segment(text, owner) or ""
        if any(marker in body for marker in GUARD_MARKERS):
            # 同一函数内已有守卫路径（如 read_zip_member 的实现本体）
            return None
    return f"{rel_path}:{node.lineno}: {reason}"


def main() -> int:
    violations = []
    for path in iter_py_files(BACKEND / "app"):
        violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())
