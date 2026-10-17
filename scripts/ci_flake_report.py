# -*- coding: utf-8 -*-
r"""CI 抖动账本（flaky ledger）—— 把 `--reruns` 掩盖掉的不确定性显式化（2026-10-17）。

背景：CI 三个后端流水线都带 `--reruns 2/3`（防真实网络/时序抖动导致假红），
但**没有任何地方记录"哪个用例重跑过"** —— 实测 2026-10-17 的 PR Checks 日志里
确实出现了 `1 rerun`，可没人知道是哪个用例。靠 rerun 转绿的用例是**被掩盖的
不确定性**：它可能是环境抖动，也可能是真实竞态（下次发布就炸在用户机器上）。

pytest-rerunfailures 的行为（本仓库实测，pytest-rerunfailures 15.0）：

* JUnit XML **不记录** rerun（单条 testcase，无失败痕迹）——不能用 XML 做账本；
* `-rR` 会输出 "rerun test summary info" 段，逐条列出 `RERUN <nodeid>`；
* 汇总行形如 `12716 passed, 10 warnings, 1 rerun in 1234.56s`。

因此本脚本解析 **文本日志**：逐条清单（若 CI 带了 `-rR`）+ 汇总计数交叉核对。

用法：
  python scripts/ci_flake_report.py --log "$RUNNER_TEMP/pytest.log" --out flaky-report.txt
  python scripts/ci_flake_report.py --log a.log --log b.log --warn-reruns 3 --max-reruns 10

退出码：0 = 正常（含"日志缺失"告警）；1 = 触发 --max-reruns 硬阈值。
"""
import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Windows 控制台编码兜底：本脚本输出中文，cp936/cp1252 下会 UnicodeEncodeError ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_RERUN_LINE_RE = re.compile(r"^RERUN\s+(\S+)")
_SUMMARY_COUNT_RE = re.compile(r"(\d+)\s+reruns?\b")


def parse_log(path: Path):
    """从单个日志文件解析 (逐条用例名计数, 汇总计数)。"""
    names = Counter()
    summary = 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        m = _RERUN_LINE_RE.match(line.strip())
        if m:
            names[m.group(1)] += 1
            continue
        # 汇总行：`1 passed, 1 rerun in 0.11s`（含 xdist 的 `N passed, M rerun` 变体）
        if "passed" in line or " in " in line:
            for found in _SUMMARY_COUNT_RE.findall(line):
                summary += int(found)
    return names, summary


def build_report(logs, warn_threshold, max_threshold):
    """产出 (报告文本, 退出码)。"""
    all_names = Counter()
    total_summary = 0
    missing = []
    for raw in logs:
        path = Path(raw)
        parsed = parse_log(path)
        if parsed is None:
            missing.append(str(path))
            continue
        names, summary = parsed
        all_names.update(names)
        total_summary += summary

    total_named = sum(all_names.values())
    lines = []
    lines.append("# CI 抖动账本（flaky ledger）")
    lines.append("")
    lines.append("生成时间: %s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    lines.append("来源日志: %s" % ", ".join(logs))
    if missing:
        lines.append("缺失日志: %s（该步骤可能早于日志创建即失败）" % ", ".join(missing))
    lines.append("")
    lines.append("- 汇总计数（pytest 汇总行）: %d rerun" % total_summary)
    lines.append("- 逐条清单（需 CI 带 `-rR`）: %d 条 / %d 个用例"
                 % (total_named, len(all_names)))
    lines.append("")
    if all_names:
        lines.append("## 发生过重跑的用例（按次数降序）")
        lines.append("")
        for nodeid, count in all_names.most_common():
            lines.append("- %d × %s" % (count, nodeid))
        lines.append("")
        lines.append("> 处置约定：同一用例**连续两轮**出现 → 先定位根因（真竞态/环境依赖），"
                     "修不掉再走隔离（标记 + 工单），**不得靠 rerun 长期掩盖**。")
    else:
        lines.append("本轮无重跑记录（或 CI 未带 `-rR`，仅汇总计数可用）。")
    lines.append("")

    exit_code = 0
    if max_threshold is not None and total_summary > max_threshold:
        lines.append("## 门禁: 失败")
        lines.append("")
        lines.append("重跑数 %d 超过硬上限 %d —— 抖动规模已不是个别用例，"
                     "需排查系统性不确定性（时序/端口/随机种子/网络）。"
                     % (total_summary, max_threshold))
        print("::error::抖动账本：重跑 %d 次 > 硬上限 %d" % (total_summary, max_threshold))
        exit_code = 1
    elif warn_threshold is not None and total_summary > warn_threshold:
        lines.append("## 门禁: 告警")
        lines.append("")
        lines.append("重跑数 %d 超过告警阈值 %d（未阻断）。" % (total_summary, warn_threshold))
        print("::warning::抖动账本：重跑 %d 次 > 告警阈值 %d" % (total_summary, warn_threshold))

    report = "\n".join(lines) + "\n"
    print(report)
    return report, exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="CI 抖动账本（解析 pytest 输出中的 rerun）")
    parser.add_argument("--log", action="append", required=True, help="pytest 文本日志（可多次）")
    parser.add_argument("--out", default="flaky-report.txt", help="报告输出路径")
    parser.add_argument("--warn-reruns", type=int, default=None, help="重跑数超过即告警（不阻断）")
    parser.add_argument("--max-reruns", type=int, default=None, help="重跑数超过即失败")
    parser.add_argument("--strict-missing", action="store_true",
                        help="日志缺失也判失败（默认仅告警）")
    args = parser.parse_args()

    report, code = build_report(args.log, args.warn_reruns, args.max_reruns)
    missing = [raw for raw in args.log if not Path(raw).exists()]
    if missing:
        print("::warning::抖动账本：%d 个日志文件不存在（步骤可能早于日志创建即失败）"
              % len(missing))
        if args.strict_missing:
            code = 1
    Path(args.out).write_text(report, encoding="utf-8")
    print("报告已写入: %s" % args.out)
    return code


if __name__ == "__main__":
    sys.exit(main())
