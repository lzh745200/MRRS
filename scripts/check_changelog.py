"""更新日志（CHANGELOG.md）时效性与格式门禁。

## 为什么需要

`CHANGELOG.md` 是本项目的**唯一账本**：对外是用户升级依据，对内是"哪次改动引出了什么后果"的
追溯起点。历史教训（v1.18.1 交付当日）——代码改了、发布也做了，但更新日志里
**既没有 E2E 选择器失效的修复，也没有"Release 正文 0 字符"与"Windows runner 上 shell 崩溃"**
这两处踩坑记录，等于把最贵的经验丢在了会话里。

靠"记得写"不可持续，故用门禁钉住以下硬要求：

1. `package.json` 的**当前版本必须在日志里有条目**（发版前必写，不许"发了但没记"）；
2. 最近 `--strict-top`（默认 3）个版本段：版本号形如 `x.y.z`、日期合法且**非未来**、
   段内**至少一条 `- ` 条目**、彼此**严格降序**（新的在上）；
3. 全文件范围内**不允许出现未来日期**（成本极低，且不会有历史误报）。

## 为什么只查"最近几段"而不是全文件

早期历史里确有不合规段（`未发布` / `Unreleased` / `1.2.0-build` 之类占位、
`1.15.8` 与 `1.2.0`/`1.1.0` 重复段）——那是当时的记录习惯，**清理它属于考古，不属于本次目标**。
门禁只保证"从今往后不再新增问题"，与仓库其它棘轮（零断言基线、硬编码色基线）的哲学一致。

## 用法

    python scripts/check_changelog.py
    python scripts/check_changelog.py --strict-top 5      # 收紧：查最近 5 段
    python scripts/check_changelog.py --today 2026-10-25  # 自测用

退出码：0 = 通过；1 = 存在问题（逐条打印原因与修复建议）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent

# `## [1.18.1] - 2026-10-24 — 标题`；标题可缺省（老格式 `## [1.0.0] - 2026-01-01`）
HEADER_RE = re.compile(r"^##\s+\[(?P<ver>[^\]]+)\]\s+-\s+(?P<date>\d{4}-\d{2}-\d{2})(?P<rest>.*)$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def parse_entries(text: str) -> list[dict]:
    """把日志切成版本段：[{version, date, body, line}]（按文件中出现顺序）。"""
    entries: list[dict] = []
    current: dict | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        match = HEADER_RE.match(raw.strip())
        if match:
            if current is not None:
                entries.append(current)
            current = {
                "version": match.group("ver").strip(),
                "date": match.group("date"),
                "title": match.group("rest").strip(" —-"),
                "lines": [],
                "line": lineno,
            }
            continue
        if current is not None:
            current["lines"].append(raw)
    if current is not None:
        entries.append(current)
    for entry in entries:
        entry["body"] = "\n".join(entry["lines"])
        entry["bullets"] = [
            line for line in entry["lines"] if line.lstrip().startswith(("- ", "* "))
        ]
    return entries


def _to_date(value: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        return None


def validate(
    entries: list[dict],
    current_version: str | None,
    today: _dt.date | None = None,
    strict_top: int = 3,
) -> list[str]:
    """返回问题列表；空列表表示通过。

    作用范围见模块 docstring：全局查「当前版本已记录」与「无未来日期」，
    格式/降序/非空只查最近 `strict_top` 段（历史遗留不追）。
    """
    problems: list[str] = []
    today = today or _dt.date.today()

    if not entries:
        return ["未找到任何 `## [x.y.z] - YYYY-MM-DD` 版本段；CHANGELOG 至少要有当前版本一条"]

    # ── 全局：未来日期（历史段日期都在过去，不会误报）────────────────
    for entry in entries:
        parsed = _to_date(entry["date"])
        if parsed is not None and parsed > today:
            problems.append(
                f"[{entry['version']}]（第 {entry['line']} 行）日期 `{entry['date']}` "
                f"晚于今天 `{today.isoformat()}`"
            )

    # ── 全局：当前版本必须已记录 ───────────────────────────────────
    seen = {entry["version"] for entry in entries}
    if current_version:
        if not VERSION_RE.match(current_version):
            problems.append(f"package.json 的 version `{current_version}` 不是 x.y.z 形式")
        elif current_version not in seen:
            problems.append(
                f"package.json 当前版本 `{current_version}` 在 CHANGELOG 中没有条目；"
                f"发版前必须在文件顶部新增 `## [{current_version}] - <今天> — <一句话主题>` 并写清变更"
            )

    # ── 最近 N 段：格式 / 非空 / 严格降序 ─────────────────────────
    window = entries[: max(strict_top, 1)]
    prev_key: tuple[int, int, int] | None = None
    for index, entry in enumerate(window):
        ver, line = entry["version"], entry["line"]
        if not VERSION_RE.match(ver):
            problems.append(f"第 {line} 行版本号 `{ver}` 不是 x.y.z 形式（最近 {len(window)} 段必须规范）")
            prev_key = None
            continue
        if not entry.get("bullets"):
            problems.append(
                f"[{ver}]（第 {line} 行）只有标题没有条目；至少写一条 `- ` 开头的变更"
            )
        key = tuple(int(part) for part in ver.split("."))
        if prev_key is not None and key >= prev_key:
            problems.append(
                f"[{ver}]（第 {line} 行）顺序错误：版本段必须**从新到旧**严格降序排列"
            )
        prev_key = key
        if index == 0 and not entry.get("title"):
            problems.append(
                f"[{ver}]（第 {line} 行）最新版本段缺少标题；写成 `## [{ver}] - <日期> — <一句话主题>`"
            )
    return problems


def read_current_version(package_json: Path) -> str | None:
    if not package_json.is_file():
        return None
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    version = data.get("version")
    return str(version) if isinstance(version, str) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CHANGELOG 时效性与格式门禁")
    parser.add_argument("--changelog", default=str(DEFAULT_ROOT / "CHANGELOG.md"))
    parser.add_argument("--package-json", default=str(DEFAULT_ROOT / "package.json"))
    parser.add_argument("--today", help="覆盖今天（YYYY-MM-DD，便于自测）")
    parser.add_argument(
        "--strict-top",
        type=int,
        default=3,
        help="严格校验最近多少个版本段（默认 3；历史遗留段不追溯）",
    )
    args = parser.parse_args(argv)

    changelog = Path(args.changelog)
    if not changelog.is_file():
        print(f"[changelog] 找不到 {changelog}", file=sys.stderr)
        return 1

    text = changelog.read_text(encoding="utf-8")
    entries = parse_entries(text)
    current = read_current_version(Path(args.package_json))
    today = _dt.date.fromisoformat(args.today) if args.today else None

    problems = validate(entries, current, today=today, strict_top=args.strict_top)
    if problems:
        print("[changelog] 更新日志门禁未通过：", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\n修复：在 CHANGELOG.md 顶部按「新 → 旧」补/改版本段，"
            "每条变更写「改了什么 + 为什么 + 怎么验证」。",
            file=sys.stderr,
        )
        return 1

    newest = entries[0]["version"]
    print(
        f"[changelog] OK：{len(entries)} 个版本段，最新 {newest}，"
        f"当前版本 {current} 已记录"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
