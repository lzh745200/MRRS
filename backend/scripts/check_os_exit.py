"""os._exit 棘轮门禁（P-1 · 遗留风险治理计划 2026-09-13）。

拦截：backend/app/** 中新增的 os._exit(...) 调用。

为什么：os._exit 直接终止进程，**lifespan shutdown 不执行** —— 调度器 Timer、
审批提醒线程、任务队列、WAL checkpoint、.part 半成品回收全部被跳过（R12-5 的
真实案例：/system/shutdown 与 /system/restart 曾长期这么干）。优雅关闭应走
signal.raise_signal(SIGINT)（见 app/api/v1/system/system.py::_graceful_shutdown）。

豁免：同一行写 nosec:os-exit <理由>。

用法::

    python backend/scripts/check_os_exit.py
    python backend/scripts/check_os_exit.py --baseline   # 收敛基线（棘轮只紧不松）
"""

import ast
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "os_exit"


def scan_text(rel_path: str, text: str) -> list:
    """返回该文件中的 os._exit 调用（行号+代码片段）。"""
    hits = []
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover - 语法错误由 ruff/flake8 拦截
        return hits
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "_exit"):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "os"):
            continue
        line = lines[node.lineno - 1] if node.lineno - 1 < len(lines) else ""
        if "nosec:os-exit" in line:
            continue
        snippet = (ast.get_source_segment(text, node) or "os._exit(...)").splitlines()[0]
        hits.append(f"{rel_path}:{node.lineno}: {snippet.strip()[:100]}")
    return hits


def main() -> int:
    violations = []
    for path in iter_py_files(BACKEND / "app"):
        violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())
