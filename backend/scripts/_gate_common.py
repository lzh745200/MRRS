"""棘轮门禁公共件（P-1/P-2/P-3，遗留风险治理计划 2026-09-13）。

设计沿用 backend/scripts/check_soft_delete_usage.py 的既有约定：

- **比对键 = 相对路径 + 归一化代码片段**（忽略行号）——无关编辑导致的
  行号漂移不会误报；真正新增的违规（新键，或同一键出现次数增加）依旧会被拦下。
- 基线文件位于 backend/scripts/gate_baselines/<gate>.txt，一行一条。
- 基线中不再命中的条目报告为 STALE（进展可见），并提示用 --baseline 收敛。
- 棘轮只紧不松：清理完历史豁免后基线应趋向空文件。
"""

import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
BASELINE_DIR = Path(__file__).resolve().parent / "gate_baselines"


def entry_key(entry: str) -> str:
    """比对键：相对路径 + 归一化代码（忽略行号）。"""
    parts = entry.split(":", 2)
    code = parts[2].strip() if len(parts) == 3 else ""
    return f"{parts[0]}::{code}"


def run_gate(gate_name: str, violations) -> int:
    """对比基线并输出结论；返回进程退出码（0=通过）。"""
    baseline_mode = "--baseline" in sys.argv
    violations = sorted({v.replace("\\", "/") for v in violations})

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    baseline_file = BASELINE_DIR / f"{gate_name}.txt"

    if baseline_mode:
        baseline_file.write_text("\n".join(violations) + "\n", encoding="utf-8")
        print(f"[baseline] {len(violations)} entries -> {baseline_file.name}")
        return 0

    known = []
    if baseline_file.exists():
        known = [
            l.strip()
            for l in baseline_file.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]

    known_counts = Counter(entry_key(k) for k in known)
    seen = Counter()
    new = []
    for v in violations:
        k = entry_key(v)
        seen[k] += 1
        if seen[k] > known_counts.get(k, 0):
            new.append(v)

    stale = [e for e in known if known_counts[entry_key(e)] > seen.get(entry_key(e), 0)]

    print(f"[gate:{gate_name}] total={len(violations)} baseline={len(known)} NEW={len(new)}")
    for v in new:
        print("NEW VIOLATION:", v)
    if stale:
        print(f"[stale] {len(stale)} 条基线豁免已不再命中（已修复），建议 --baseline 收敛：")
        for e in stale:
            print("STALE BASELINE:", e)
    return 1 if new else 0


def iter_py_files(root: Path):
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND)).replace("\\", "/")
    except ValueError:  # pragma: no cover - 仅当传入 BACKEND 之外的路径
        return str(path).replace("\\", "/")
