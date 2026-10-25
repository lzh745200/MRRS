"""分页上限门禁：`page_size` 必须有显式上限，且不得超过 `MAX_PAGE_SIZE`。

## 为什么

离线单机系统里"一次拉太多"不是慢一点，而是**把内存吃穿**：SQLite 一行携带多列文本
（含加密 PII 列）时，`page_size=1000` 就可能是几十 MB 的 ORM 对象图；Electron 渲染进程
拿到超大 JSON 会直接卡死（现场表现是"点一下列表就白屏"）。

历史状态（2026-10-25 排查）：55 处声明里 51 处写了 `le=100/200`，但有 **4 处是裸 int**
（`page_size: int = 20`），等于把上限交给了调用方 —— 没有任何一处会因为参数过大而拒绝请求。
本门禁把"必须有上限"固化下来：

1. 任何名为 `page_size` 的参数/字段声明，**同行必须含 `le=`**（或显式引用 `MAX_PAGE_SIZE`）；
2. `le=` 的字面量不得大于 `app/core/constants.py` 的 `MAX_PAGE_SIZE`。

## 用法

    python backend/scripts/check_pagination_cap.py
    python backend/scripts/check_pagination_cap.py --root backend

退出码：0 = 通过；1 = 存在无上限或超上限的分页参数。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PAGE_SIZE_RE = re.compile(r"^\s*page_size\s*:\s*int\s*=\s*(?P<rest>.+)$")
LE_RE = re.compile(r"\ble\s*=\s*(?P<val>MAX_PAGE_SIZE|\d+)")
MAX_DEFAULT = 100


def _max_page_size(constants_py: Path) -> int:
    try:
        text = constants_py.read_text(encoding="utf-8")
    except OSError:
        return MAX_DEFAULT
    match = re.search(r"^MAX_PAGE_SIZE\s*=\s*(\d+)", text, re.MULTILINE)
    return int(match.group(1)) if match else MAX_DEFAULT


def scan(root: Path, max_allowed: int) -> list[str]:
    problems: list[str] = []
    api_dir = root / "app" / "api"
    if not api_dir.is_dir():
        return [f"找不到 {api_dir}（--root 应指向 backend 目录）"]
    for py in sorted(api_dir.rglob("*.py")):
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            match = PAGE_SIZE_RE.match(line)
            if not match:
                continue
            rest = match.group("rest")
            le = LE_RE.search(rest)
            rel = py.relative_to(root).as_posix()
            if not le:
                problems.append(
                    f"{rel}:{lineno}  page_size 没有上限（同行缺 le=）—— 加 "
                    f"Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE) 或 Field(...)"
                )
                continue
            val = le.group("val")
            if val.isdigit() and int(val) > max_allowed:
                problems.append(
                    f"{rel}:{lineno}  page_size 上限 le={val} 超过 MAX_PAGE_SIZE={max_allowed}"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="分页上限门禁（page_size 必须 le=MAX_PAGE_SIZE）")
    parser.add_argument("--root", default="backend", help="backend 目录（默认 backend）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    max_allowed = _max_page_size(root / "app" / "core" / "constants.py")
    problems = scan(root, max_allowed)

    if problems:
        print("[pagination-cap] 分页上限门禁未通过：", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"[pagination-cap] OK：page_size 均带上限且不超过 MAX_PAGE_SIZE={max_allowed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
