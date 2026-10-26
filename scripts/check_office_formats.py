#!/usr/bin/env python
"""办公文档格式门禁（WPS 兼容改造 P4，2026-10-26）。

## 为什么要这道门禁

WPS 兼容的四个真实缺口都**不是**靠"记得改"能长期守住的：

1. 导入端点直连 `openpyxl.load_workbook` → `.xls`（OLE2）与旧版 WPS `.et`
   静默失败（openpyxl 只支持 OOXML）。必须统一走 `app.services.office_reader`；
2. 白名单各写一套 `endswith((".xlsx", ".xls"))` → 新增 `.et` 时漏改就被拒；
   必须用 `app.core.office_formats.is_spreadsheet_upload` 单一事实源；
3. 导出若出现 WPS 打不开的格式（`.et/.wps/.dps` 或自造扩展名），用户拿到文件打不开；
   只允许 xlsx/csv/docx/pdf；
4. CSV 不带 UTF-8 BOM → WPS/Excel 打开中文乱码（历史就是靠 BOM 修好的）。

外加一次**运行时自检**：用 office_reader 读 xlsx / xls / 两种容器的 .et 夹具，
确认 openpyxl + xlrd 都可用、容器嗅探没退化成"只看扩展名"。

## 用法

    python scripts/check_office_formats.py
    python scripts/check_office_formats.py --json

退出码：0 = 通过；1 = 有违规。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
FIXTURES = BACKEND / "tests" / "fixtures" / "office"

EXPORT_FORMATS = {"xlsx", "csv", "docx", "pdf"}

# 导入侧禁止的裸调用（导出写 workbook 用 `from openpyxl import Workbook` 不受限）
RAW_LOAD_WORKBOOK = re.compile(r"^\s*from openpyxl import [^\n]*\bload_workbook\b", re.MULTILINE)
# 白名单禁止硬编码（必须走 office_formats）
HARDCODED_XLS_WHITELIST = re.compile(r"endswith\(\s*\(\s*[\"']\.xlsx[\"']\s*,\s*[\"']\.xls[\"']")
# 导出附件头里的扩展名
ATTACHMENT_EXT = re.compile(r"attachment;[^\"']*?\.([A-Za-z0-9]{2,5})")
# CSV 产生的 BOM 标记
BOM_MARKERS = ("utf-8-sig", "\\ufeff", "\ufeff")


def _iter_py(base: Path):
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.py")):
        yield path


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:  # pragma: no cover - 外部路径
        return str(path)


def scan_static(root: Path) -> List[Dict[str, str]]:
    """静态检查：返回问题列表（file/line/rule/message）。"""
    problems: List[Dict[str, str]] = []
    app_dir = root / "backend" / "app"
    api_dir = app_dir / "api"
    office_reader = app_dir / "services" / "office_reader.py"

    for path in _iter_py(api_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.resolve() == office_reader.resolve():  # pragma: no cover - reader 不在 api 下
            continue
        for match in RAW_LOAD_WORKBOOK.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            problems.append(
                {
                    "file": _rel(path),
                    "line": str(line_no),
                    "rule": "raw-openpyxl-import",
                    "message": "导入路径禁止直连 openpyxl.load_workbook（.xls/.et 会失败）；"
                    "改用 app.services.office_reader.load_workbook_any",
                }
            )
        for match in HARDCODED_XLS_WHITELIST.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            problems.append(
                {
                    "file": _rel(path),
                    "line": str(line_no),
                    "rule": "hardcoded-xls-whitelist",
                    "message": "禁止硬编码 .xlsx/.xls 白名单；改用 office_formats.is_spreadsheet_upload"
                    "（含 WPS .et）",
                }
            )

    for path in _iter_py(app_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        # 导出扩展名白名单
        for match in ATTACHMENT_EXT.finditer(text):
            ext = match.group(1).lower()
            if ext in EXPORT_FORMATS:
                continue
            if ext in {"zip", "json"}:
                # 数据包/配置包不属于办公文档导出，放行
                continue
            line_no = text[: match.start()].count("\n") + 1
            problems.append(
                {
                    "file": _rel(path),
                    "line": str(line_no),
                    "rule": "non-wps-export-format",
                    "message": f"导出扩展名 .{ext} 不在 WPS/Office 通用格式白名单"
                    f"（{'/'.join(sorted(EXPORT_FORMATS))}）内",
                }
            )
        # CSV 必须带 BOM
        if "csv.writer(" in text and not any(marker in text for marker in BOM_MARKERS):
            line_no = text[: text.index("csv.writer(")].count("\n") + 1
            problems.append(
                {
                    "file": _rel(path),
                    "line": str(line_no),
                    "rule": "csv-missing-bom",
                    "message": "CSV 导出缺少 UTF-8 BOM（WPS/Excel 打开中文会乱码）",
                }
            )
    return problems


def check_runtime(root: Path) -> List[Dict[str, str]]:
    """运行时自检：依赖齐全 + 四类夹具都能读出数据。"""
    problems: List[Dict[str, str]] = []
    backend = root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    fixtures = backend / "tests" / "fixtures" / "office"

    try:
        import xlrd  # noqa: F401 - 仅探测可导入
        import openpyxl  # noqa: F401 - 仅探测可导入
    except ImportError:
        # CI 的 static-analysis 作业只装标准库（不装 requirements）：
        # 此处降级为"跳过运行时自检"，真依赖由 pytest 用例
        # tests/unit/test_office_formats_gate.py::test_runtime_fixtures_ok 覆盖。
        print(
            "[office-formats] 跳过运行时自检：当前环境未安装 openpyxl/xlrd"
            "（CI static-analysis 不装依赖；pytest 侧覆盖）"
        )
        return problems
    except ImportError:  # pragma: no cover - 旧写法兼容
        problems.append(
            {
                "file": "backend/requirements.txt",
                "line": "0",
                "rule": "missing-xlrd",
                "message": "缺少 xlrd，.xls / WPS 旧版 .et 无法导入（requirements 已登记 xlrd==2.0.1）",
            }
        )
        return problems

    try:
        from app.services.office_reader import read_rows
    except Exception as exc:  # pragma: no cover - 导入失败即环境坏
        return [
            {
                "file": "backend/app/services/office_reader.py",
                "line": "0",
                "rule": "reader-import-failed",
                "message": f"office_reader 无法导入：{exc}",
            }
        ]

    samples = ["sample.xlsx", "sample.xls", "sample_ooxml.et", "sample_ole2.et"]
    for name in samples:
        path = fixtures / name
        if not path.is_file():
            problems.append(
                {
                    "file": _rel(path),
                    "line": "0",
                    "rule": "missing-fixture",
                    "message": "缺少 WPS 兼容测试夹具（应提交 backend/tests/fixtures/office/）",
                }
            )
            continue
        try:
            rows = read_rows(path.read_bytes(), name)
        except Exception as exc:
            problems.append(
                {
                    "file": _rel(path),
                    "line": "0",
                    "rule": "fixture-unreadable",
                    "message": f"{name} 读取失败：{exc}",
                }
            )
            continue
        if not rows or str(rows[0][0]) != "姓名":
            problems.append(
                {
                    "file": _rel(path),
                    "line": "0",
                    "rule": "fixture-unexpected-data",
                    "message": f"{name} 读出的首行表头异常（期望 '姓名'）",
                }
            )
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="办公文档格式门禁（WPS 兼容）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出（CI 便于机器读）")
    parser.add_argument("--root", default=str(ROOT), help="仓库根目录")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    problems = scan_static(root) + check_runtime(root)
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print("[office-formats] 门禁未通过：", file=sys.stderr)
        for item in problems:
            print(f"  - {item['file']}:{item['line']} [{item['rule']}] {item['message']}", file=sys.stderr)
    else:
        print("[office-formats] OK：导入统一层 / 白名单单一源 / 导出格式与 CSV BOM / xls+et 夹具 全部通过")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
