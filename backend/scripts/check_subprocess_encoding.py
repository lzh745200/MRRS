"""subprocess 编码棘轮门禁（P-1 · 遗留风险治理计划 2026-09-13）。

拦截：backend/{app,tests}/** 中 subprocess.run/Popen/check_output/check_call 使用
text=True / universal_newlines=True 却**未显式指定 encoding**。

为什么：Windows 下父进程按控制台代码页（GBK）解码子进程输出，子进程输出含
非 GBK 字节时 reader 线程抛 UnicodeDecodeError（v1.12.3 Windows 出包门禁崩溃、
v1.12.6 管道解码 3 例失败的同类先例）。

豁免：同一行写 nosec:subprocess-encoding <理由>。

用法::

    python backend/scripts/check_subprocess_encoding.py
    python backend/scripts/check_subprocess_encoding.py --baseline
"""

import ast
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "subprocess_encoding"
SUBPROCESS_FUNCS = {"run", "Popen", "check_output", "check_call", "call"}
SCAN_DIRS = ("app", "tests")


def scan_text(rel_path: str, text: str) -> list:
    hits = []
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover
        return hits
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if not (isinstance(owner, ast.Name) and owner.id == "subprocess"):
            continue
        if node.func.attr not in SUBPROCESS_FUNCS:
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        text_flag = any(
            isinstance(v, ast.Constant) and v.value is True
            for k, v in kwargs.items()
            if k in ("text", "universal_newlines")
        )
        if not text_flag or "encoding" in kwargs:
            continue
        line = lines[node.lineno - 1] if node.lineno - 1 < len(lines) else ""
        if "nosec:subprocess-encoding" in line:
            continue
        hits.append(f"{rel_path}:{node.lineno}: subprocess.{node.func.attr}(text=True 缺 encoding)")
    return hits


def main() -> int:
    violations = []
    for sub in SCAN_DIRS:
        for path in iter_py_files(BACKEND / sub):
            violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())
