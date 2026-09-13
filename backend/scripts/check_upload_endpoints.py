"""上传端点合规棘轮门禁（P-3 · 遗留风险治理计划 2026-09-13）。

拦截：backend/app/api/** 中带 UploadFile 参数的路由处理函数，既未调用
read_upload_with_limit(...) / save_upload_file(...)，也未走流式落盘
（shutil.copyfileobj）。

为什么（R2 根因的制度化）：端点层 18 处历史写法 await file.read() 先把整包
读进内存再比较长度，校验只能拒绝请求、挡不住内存峰值。新增端点必须显式
声明上限，否则重蹈覆辙。

豁免：函数内写 nosec:upload-limit <理由>；历史合法点写进基线
（backend/scripts/gate_baselines/upload_endpoints.txt）。

用法::

    python backend/scripts/check_upload_endpoints.py
    python backend/scripts/check_upload_endpoints.py --baseline
"""

import ast
import re
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "upload_endpoints"
ACCEPTED_MARKERS = (
    "read_upload_with_limit(",
    "save_upload_file(",
    "copyfileobj(",
    "read_zip_member(",
    "ensure_zip_within_limit(",
    "nosec:upload-limit",
)
# 带长度参数的分块读同样合规：await file.read(8 * 1024 * 1024)（有界峰值）
BOUNDED_READ_RE = re.compile(r"\.read\(\s*[^)\s]")


def _is_compliant(body: str) -> bool:
    return any(marker in body for marker in ACCEPTED_MARKERS) or bool(BOUNDED_READ_RE.search(body))


def scan_text(rel_path: str, text: str) -> list:
    hits = []
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover
        return hits

    handlers = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        upload_args = [
            arg
            for arg in list(node.args.args) + list(node.args.kwonlyargs)
            if isinstance(arg.annotation, ast.Name) and arg.annotation.id == "UploadFile"
        ]
        if not upload_args:
            continue
        body = ast.get_source_segment(text, node) or ""
        handlers.append((node, body, upload_args))

    # 一级委托：函数体调用同文件内的合规处理函数（如 _stream_package_to_disk）
    # 也算合规 —— 被委托者自身同样受本门禁扫描，不会形成豁免黑洞。
    compliant_names = {node.name for node, body, _ in handlers if _is_compliant(body)}

    for node, body, upload_args in handlers:
        if _is_compliant(body):
            continue
        if any(name in body for name in compliant_names if name != node.name):
            continue
        names = ", ".join(a.arg for a in upload_args)
        hits.append(
            f"{rel_path}:{node.lineno}: {node.name}({names}) 未限长读取"
            f"（read_upload_with_limit/save_upload_file/流式落盘/带长度参数的分块读）"
        )
    return hits


def main() -> int:
    violations = []
    for path in iter_py_files(BACKEND / "app" / "api"):
        violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())
