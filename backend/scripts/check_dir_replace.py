"""目录替换棘轮门禁（P-1 · 遗留风险治理计划 2026-09-13）。

拦截：shutil.rmtree(..., ignore_errors=True) 之后 5 行内出现 copytree(...)，
但该 copytree **未带 dirs_exist_ok=True**。

为什么：Windows 上 rmtree 因文件被占用而静默失败（ignore_errors=True 吞掉
PermissionError）后，紧随的 copytree 目标目录仍存在 → FileExistsError，
整条恢复/替换链路崩溃且原因指向"目录已存在"，与真实根因（占用）相距甚远。

豁免：同一行写 nosec:dir-replace <理由>。

用法::

    python backend/scripts/check_dir_replace.py
    python backend/scripts/check_dir_replace.py --baseline
"""

import re
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "dir_replace"
RMTREE_RE = re.compile(r"rmtree\([^)]*ignore_errors\s*=\s*True")
COPYTREE_RE = re.compile(r"copytree\(")
WINDOW = 5


def scan_text(rel_path: str, text: str) -> list:
    lines = text.splitlines()
    hits = []
    for idx, line in enumerate(lines):
        if not RMTREE_RE.search(line) or "nosec:dir-replace" in line:
            continue
        window = lines[idx: idx + WINDOW + 1]
        for offset, candidate in enumerate(window):
            if not COPYTREE_RE.search(candidate):
                continue
            # dirs_exist_ok 可能写在同一行，也可能分布在紧随其后的参数行
            call_block = " ".join(window[offset: offset + 4])
            if "dirs_exist_ok" in call_block:
                continue
            if "nosec:dir-replace" in candidate:
                continue
            hits.append(
                f"{rel_path}:{idx + offset + 1}: rmtree(ignore_errors=True) 后的 "
                f"copytree 缺少 dirs_exist_ok=True"
            )
            break
    return hits


def main() -> int:
    violations = []
    for path in iter_py_files(BACKEND / "app"):
        violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())
