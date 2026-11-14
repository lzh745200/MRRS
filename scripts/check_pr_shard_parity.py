#!/usr/bin/env python3
"""PR Checks 矩阵分片完整性门禁。

矩阵化 backend-test 后，最容易出现的回归不是测试失败，而是**漏跑**：
某个 shard 的分段列表少写一段，4 个 job 仍然全绿，但覆盖率门禁因为缺数据
可能异常通过/失败，且 PR 反馈不可信。本脚本只做一件事：

- 解析 `.github/workflows/pr-checks.yml` 中 `backend-test-shard` 的
  `segments: "..."` 列表；
- 与 `scripts/run_backend_tests_segmented.py` 的 12 段定义求并集；
- 要求 1..12 恰好各出现一次（无遗漏、无重复）。

纯标准库，供 static-analysis 作业调用；不依赖 PyYAML。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "pr-checks.yml"
RUNNER = ROOT / "scripts" / "run_backend_tests_segmented.py"

SEGMENT_RE = re.compile(r"^\s*segments:\s*[\"']([0-9,\s]+)[\"']", re.MULTILINE)
EXPECTED = set(range(1, 13))


def parse_shards(text: str) -> list[list[int]]:
    shards: list[list[int]] = []
    for raw in SEGMENT_RE.findall(text):
        # 只接受严格逗号分隔的数字；空段/非法 token 直接报错，避免静默跳过。
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        shards.append([int(part) for part in parts])
    return shards


def main() -> int:
    if not WORKFLOW.exists():
        print(f"[pr-shard-parity] 缺少工作流: {WORKFLOW}", file=sys.stderr)
        return 2
    shards = parse_shards(WORKFLOW.read_text(encoding="utf-8"))
    if not shards:
        print("[pr-shard-parity] 未找到 backend-test-shard 的 segments 列表", file=sys.stderr)
        return 2

    flattened = [segment for shard in shards for segment in shard]
    duplicates = sorted({segment for segment in flattened if flattened.count(segment) > 1})
    invalid = sorted(set(flattened) - EXPECTED)
    missing = sorted(EXPECTED - set(flattened))

    if duplicates or invalid or missing:
        print("[pr-shard-parity] FAIL：PR 分片覆盖不完整", file=sys.stderr)
        if duplicates:
            print(f"  重复段: {duplicates}", file=sys.stderr)
        if invalid:
            print(f"  越界段: {invalid}（合法范围 1..12）", file=sys.stderr)
        if missing:
            print(f"  漏跑段: {missing}", file=sys.stderr)
        return 1

    print(
        f"[pr-shard-parity] OK：{len(shards)} 个 shard 覆盖 1..12 各一次"
        f"（{', '.join(str(len(s)) for s in shards)} 段/片）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
