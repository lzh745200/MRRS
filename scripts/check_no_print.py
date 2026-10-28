#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""禁止生产代码使用 print 的行为门禁（日志唯一出口是 logger）。

## 为什么

桌面版后端最终跑在 Electron 里（无控制台窗口），print 的输出**用户与我们永远看不到**：
现场排障时日志里没有、审计里没有、崩溃报告里也没有。2026-10-28 体检用精确正则复核：
backend/app 下真正的 print 语句只有 3 处，且都在"logger 还不能用"的启动/关闭兜底路径上
（main.py 的启动进度条、logging_config 的 handler 关闭失败兜底）——这三处属**允许项**，
其余任何新 print 都视为回归。

注：早先按 \"print(\" 粗匹配得到 38 处是**误报**（命中了 fingerprint( / setup_print( 等），
本门禁用行首锚定避免同类误伤。

用法::

    python scripts/check_no_print.py
    python scripts/check_no_print.py --json

退出码：0 = 无新增 print；1 = 发现允许项之外的 print。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# 行首锚定 + 允许缩进：只匹配语句，不误伤 fingerprint( / setup_print( 等标识符
PRINT_RE = re.compile(r"^\s*print\s*\(", re.MULTILINE)

# 允许项：启动横幅（logger 尚未就绪）与日志系统自身故障兜底（logger 已不可用）
ALLOWED: Dict[str, str] = {
    "app/main.py": "启动进度条：logger 未就绪，且这是人读的启动横幅",
    "app/core/logging_config.py": "日志 handler 关闭失败兜底：此时 logger 已不可用",
}


def scan(app_dir: Path = APP) -> List[dict]:
    problems: List[dict] = []
    if not app_dir.is_dir():
        return [{"file": str(app_dir), "line": 0, "message": "找不到 backend/app 目录"}]
    for path in sorted(app_dir.rglob("*.py")):
        rel = path.relative_to(app_dir.parent).as_posix()
        if rel in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in PRINT_RE.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            problems.append({
                "file": rel,
                "line": line_no,
                "message": "生产代码禁止 print：改用模块 logger（日志才能在桌面端可见）",
            })
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="禁止生产代码 print（日志统一走 logger）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    problems = scan()
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print("[no-print] 发现 %d 处 print：" % len(problems), file=sys.stderr)
        for item in problems:
            print("  - %s:%d %s" % (item["file"], item["line"], item["message"]), file=sys.stderr)
        print("  允许项（启动/日志兜底）：" + ", ".join(sorted(ALLOWED)), file=sys.stderr)
    else:
        print("[no-print] OK：仅保留 %d 处允许项（启动横幅/日志兜底）" % len(ALLOWED))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
