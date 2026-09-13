"""周期任务注册棘轮门禁（P-2 · 遗留风险治理计划 2026-09-13）。

拦截：backend/app/** 中新增的裸 threading.Timer(...) —— 周期任务必须走
app/services/backup_scheduler.py 的 RecurringTimer（统一登记、可 stop、可 join、
带看门狗、/health 可见）。

为什么（R8 根因）：历史上 daily/weekly 自我重排 Timer 重复 append 到 _timers
（慢性泄漏）、interval 重排 Timer 从不入表（stop 取消不到）、_job 先执行后重排
且无超时（作业卡死即链断，自动备份永久静默停止）。

豁免：文件级白名单（下方 ALLOWED_FILES，须注明理由）或同一行写
nosec:scheduler-registration <理由>。

用法::

    python backend/scripts/check_scheduler_registration.py
    python backend/scripts/check_scheduler_registration.py --baseline
"""

import re
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "scheduler_registration"
TIMER_RE = re.compile(r"\bthreading\.Timer\(")

# 文件级豁免：路径 -> 理由（新增必须写明为什么不能走 RecurringTimer）
ALLOWED_FILES = {
    # RecurringTimer 的唯一实现处：周期任务的调度原语就在这里
    "app/services/backup_scheduler.py": "RecurringTimer 实现本体",
    # 一次性（非周期）延迟动作：内部 shutdown 端点 0.5s 后触发 SIGINT
    "app/main.py": "内部 shutdown 一次性延迟信号，非周期任务",
}


def scan_text(rel_path: str, text: str) -> list:
    if rel_path in ALLOWED_FILES:
        return []
    hits = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if not TIMER_RE.search(line) or "nosec:scheduler-registration" in line:
            continue
        hits.append(f"{rel_path}:{idx}: {line.strip()[:100]}")
    return hits


def main() -> int:
    violations = []
    for path in iter_py_files(BACKEND / "app"):
        violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())
