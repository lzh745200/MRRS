"""把覆盖率缺口渲染成「人可以直接照着修」的清单（Markdown）。

## 为什么需要

`fail_under=100` 只会让 CI **红一次**：谁也不知道缺哪几行，于是常见结局是
「本地补个 skip/pragma 糊过去」。本脚本把缺口语义化：

- 后端 `coverage.py` 的 JSON（`coverage-branch.json` / `coverage.json`）→ `missing_lines` / `missing_branches`
- 前端 istanbul 的 `coverage-final.json` → 由 `statementMap` + `s` 反推未执行语句行

输出写到 `$GITHUB_STEP_SUMMARY`（运行页直接可见，**不需要任何额外权限**，
也不像 `pull-requests: write` 那样在受限仓库里失败）并作为 artifact 留存。

## 用法

    python scripts/coverage_gaps.py --coveragepy backend/coverage-branch.json
    python scripts/coverage_gaps.py --istanbul frontend/coverage/coverage-final.json
    python scripts/coverage_gaps.py --coveragepy a.json --out gaps.md --top 20 --max-lines 15
    python scripts/coverage_gaps.py --selftest        # 内置双格式自测

退出码：始终 0（这是**报告**不是门禁；门禁仍是 `fail_under=100`）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:  # pragma: no cover - 环境相关（中文 Windows 控制台 gbk）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _is_coveragepy(data: object) -> bool:
    return isinstance(data, dict) and "files" in data and isinstance(data.get("files"), dict)


def parse_coveragepy(data: dict) -> dict[str, dict]:
    """→ {file: {"lines": [...], "branches": n}}（只保留有缺口的文件）。"""
    out: dict[str, dict] = {}
    for name, info in (data.get("files") or {}).items():
        if not isinstance(info, dict):
            continue
        missing = list(info.get("missing_lines") or [])
        branches = len(info.get("missing_branches") or [])
        if missing or branches:
            out[name] = {"lines": missing, "branches": branches}
    return out


def parse_istanbul(data: dict) -> dict[str, dict]:
    """istanbul `coverage-final.json`：由 statementMap + s 反推未执行语句行。"""
    out: dict[str, dict] = {}
    for name, info in data.items():
        if not isinstance(info, dict):
            continue
        statement_map = info.get("statementMap") or {}
        counts = info.get("s") or {}
        if not isinstance(statement_map, dict) or not isinstance(counts, dict):
            continue
        lines: set[int] = set()
        for sid, meta in statement_map.items():
            if counts.get(sid, 0) == 0 and isinstance(meta, dict):
                start = meta.get("start") or {}
                line = start.get("line")
                if isinstance(line, int):
                    lines.add(line)
        branch_map = info.get("branchMap") or {}
        branch_counts = info.get("b") or {}
        branches = 0
        for bid, meta in branch_map.items():
            hit = branch_counts.get(bid)
            if isinstance(hit, list):
                branches += sum(1 for c in hit if c == 0)
            elif hit == 0:
                branches += 1
        if lines or branches:
            # 统一成仓库相对路径，便于在 PR 里 Ctrl+Click
            key = name
            marker = "frontend"
            idx = name.replace("\\", "/").find(f"/{marker}/")
            if idx >= 0:
                key = name.replace("\\", "/")[idx + 1 :]
            out[key] = {"lines": sorted(lines), "branches": branches}
    return out


def _fmt_lines(lines: list[int], max_lines: int) -> str:
    if not lines:
        return "—"
    head = ", ".join(str(n) for n in lines[:max_lines])
    return head + (f" …(+{len(lines) - max_lines})" if len(lines) > max_lines else "")


def render(gaps: dict[str, dict], *, title: str, top: int, max_lines: int) -> str:
    total_files = len(gaps)
    total_points = sum(len(g["lines"]) for g in gaps.values())
    total_branches = sum(g["branches"] for g in gaps.values())
    if not gaps:
        return f"### {title}\n\n无缺口：所有可执行行与分支均已覆盖。\n"

    ranked = sorted(
        gaps.items(),
        key=lambda kv: (len(kv[1]["lines"]), kv[1]["branches"]),
        reverse=True,
    )[:top]
    lines = [
        f"### {title}",
        "",
        f"- 有缺口文件：**{total_files}**；未覆盖语句行：**{total_points}**；未覆盖分支：**{total_branches}**",
        f"- 下表按缺口从大到小，仅列前 **{len(ranked)}** 个文件（每文件最多 {max_lines} 行）",
        "",
        "| 文件 | 未覆盖行数 | 未覆盖分支 | 未覆盖行 |",
        "|------|-----------:|-----------:|----------|",
    ]
    for name, gap in ranked:
        lines.append(
            f"| `{name}` | {len(gap['lines'])} | {gap['branches']} | {_fmt_lines(gap['lines'], max_lines)} |"
        )
    lines.append("")
    lines.append("> 补测请直接照着「未覆盖行」写用例；**不要**用 `pragma: no cover` / `skip` 糊过去（有豁免理由棘轮）。")
    return "\n".join(lines) + "\n"


def _load(path: Path) -> object:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _autodetect(path: Path) -> tuple[str, dict[str, dict]]:
    data = _load(path)
    if _is_coveragepy(data):
        return "coverage.py", parse_coveragepy(data)  # type: ignore[arg-type]
    if isinstance(data, dict):
        return "istanbul", parse_istanbul(data)
    raise ValueError(f"无法识别的覆盖率格式：{path}")


SELFTEST_COVERAGEPY = {
    "meta": {},
    "files": {
        "app/ok.py": {"missing_lines": [], "missing_branches": []},
        "app/gap.py": {"missing_lines": [12, 13, 20], "missing_branches": [21, 22]},
    },
    "totals": {},
}
SELFTEST_ISTANBUL = {
    "/repo/frontend/src/a.vue": {
        "statementMap": {"0": {"start": {"line": 5}}, "1": {"start": {"line": 9}}},
        "s": {"0": 1, "1": 0},
        "branchMap": {"0": {}},
        "b": {"0": [0, 1]},
    },
    "/repo/frontend/src/b.ts": {
        "statementMap": {"0": {"start": {"line": 2}}},
        "s": {"0": 3},
        "branchMap": {},
        "b": {},
    },
}


def _selftest() -> int:
    cg = parse_coveragepy(SELFTEST_COVERAGEPY)
    assert set(cg) == {"app/gap.py"}, cg
    assert cg["app/gap.py"]["lines"] == [12, 13, 20]
    assert cg["app/gap.py"]["branches"] == 2

    ib = parse_istanbul(SELFTEST_ISTANBUL)
    assert set(ib) == {"frontend/src/a.vue"}, ib
    assert ib["frontend/src/a.vue"]["lines"] == [9]
    assert ib["frontend/src/a.vue"]["branches"] == 1

    md = render(cg, title="T", top=5, max_lines=2)
    assert "app/gap.py" in md and "12, 13 …(+1)" in md
    assert "无缺口" in render({}, title="T", top=5, max_lines=2)
    print("[coverage-gaps] selftest OK（coverage.py 与 istanbul 双格式）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="覆盖率缺口 → Markdown 清单（报告，非门禁）")
    parser.add_argument("--coveragepy", help="coverage.py 生成的 JSON")
    parser.add_argument("--istanbul", help="istanbul coverage-final.json")
    parser.add_argument("--out", help="写入文件（默认 stdout）")
    parser.add_argument("--title", default="覆盖率缺口")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--max-lines", type=int, default=12)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.coveragepy and not args.istanbul:
        parser.error("需要 --coveragepy 或 --istanbul 之一（或用 --selftest）")

    sections: list[str] = []
    for raw, label in ((args.coveragepy, "后端"), (args.istanbul, "前端")):
        if not raw:
            continue
        path = Path(raw)
        if not path.is_file():
            sections.append(f"### {args.title}（{label}）\n\n未找到 `{raw}`（该作业可能未跑到覆盖率步骤）。\n")
            continue
        try:
            _kind, gaps = _autodetect(path)
        except (json.JSONDecodeError, ValueError) as exc:
            sections.append(f"### {args.title}（{label}）\n\n无法解析 `{raw}`：{exc}\n")
            continue
        sections.append(render(gaps, title=f"{args.title}（{label}）", top=args.top, max_lines=args.max_lines))

    text = "\n".join(sections)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[coverage-gaps] 已写入 {args.out}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(text)
            print("[coverage-gaps] 已追加到 GITHUB_STEP_SUMMARY")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
