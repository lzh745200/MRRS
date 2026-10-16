# -*- coding: utf-8 -*-
"""一次性文档工具（R28）：把两份介绍 PPT 的版本/日期/用例口径统一到 v1.12.17。

背景（T5 待办 · ppt）：
  两份 PPT（docs/帮扶管理信息系统介绍.pptx 与根目录同名文件）停在 v1.12.15 / 12,422 / 6,323，
  与本轮发布（v1.12.17）的实测口径不一致。

用法：
  cd backend && .venv313/Scripts/python.exe ../scripts/update_pptx_versions_20261016.py \
      --backend-cases 12604 --frontend-cases 6340

行为：
  1. 先备份到 .scratch/w16-r28-fix/ppt-backup-<日期>/；
  2. 文本框与表格单元格里把 1.12.15 / 12,422 / 6,323 / 2026-10-08 换成新值；
  3. 只替换上述**目标字面量**，历史版本（v1.11.1 / v1.12.4 / v1.12.5…）不动。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from pptx import Presentation

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "docs" / "帮扶管理信息系统介绍.pptx",
    ROOT / "帮扶管理信息系统介绍.pptx",
]
BACKUP_DIR = ROOT / ".scratch" / "w16-r28-fix" / f"ppt-backup-{date.today().isoformat()}"

OLD_VERSION = "1.12.15"
NEW_VERSION = "1.12.17"
OLD_BACKEND_CASES = "12,422"
OLD_FRONTEND_CASES = "6,323"
OLD_SOURCE_DATE = "2026-10-08"


def _replace_in_tf(text_frame, pairs) -> int:
    n = 0
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            text = run.text
            new = text
            for old, repl in pairs:
                new = new.replace(old, repl)
            if new != text:
                run.text = new
                n += 1
    return n


def replace_in_slide(slide, pairs) -> int:
    n = 0
    for shape in slide.shapes:
        if shape.has_text_frame:
            n += _replace_in_tf(shape.text_frame, pairs)
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    n += _replace_in_tf(cell.text_frame, pairs)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-date", default=date.today().isoformat(),
                    help="替换「数据来源：<日期>」中的日期")
    ap.add_argument("--backend-cases", default=None, help="后端用例数（千分位，如 12,604）")
    ap.add_argument("--frontend-cases", default=None, help="前端用例数（千分位，如 6,340）")
    args = ap.parse_args()

    pairs = [(OLD_VERSION, NEW_VERSION), (OLD_SOURCE_DATE, args.source_date)]
    if args.backend_cases:
        pairs.append((OLD_BACKEND_CASES, args.backend_cases))
    if args.frontend_cases:
        pairs.append((OLD_FRONTEND_CASES, args.frontend_cases))

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for pptx in TARGETS:
        if not pptx.exists():
            print(f"[skip] 不存在: {pptx}")
            continue
        backup = BACKUP_DIR / pptx.name
        if not backup.exists():
            shutil.copy2(pptx, backup)

        prs = Presentation(str(pptx))
        replaced = 0
        for slide in prs.slides:
            replaced += replace_in_slide(slide, pairs)
        prs.save(str(pptx))
        print(f"{pptx.name}: 替换 {replaced} 处 run, 幻灯片 {len(prs.slides)} 页, 备份 {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
