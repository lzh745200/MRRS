#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""错误文案泄漏门禁 —— 禁止把 axios 技术原文展示给用户

## 为什么需要

2026-10-25 用户反馈界面出现 ``Request failed with status code 422``。

axios 在 4xx/5xx 时把 ``error.message`` 设成
``Request failed with status code <状态码>`` 这类**开发者文案**。
一旦视图里写成 ``ElMessage.error(error.message)``，用户看到的就是英文技术串。

修复分三层（本门禁守第三层）：
1. 后端把 422 的 ``detail`` 中文化并给 ``message``（``app/core/validation_errors.py``）；
2. 前端统一出口 ``getErrorMessage()`` 保证永不返回技术原文
   （``src/utils/getErrorMessage.ts``）；
3. **本门禁**：扫描 ``frontend/src``，发现面向用户的提示调用里直接取
   ``error.message`` / ``err.message`` / ``e.message`` 即失败。

## 判定的口径

只拦"直接展示"：``ElMessage.*`` / ``ElNotification.*`` / ``notify(...)``
的实参里出现 ``<变量>.message``，且该变量是错误对象（err/error/e/ex/exception）。
``getErrorMessage(error)`、日志（``logger.error(..., error.message)``）不算泄漏。

## 用法

    python scripts/check_error_message_leaks.py          # 0=干净 1=有泄漏
    python scripts/check_error_message_leaks.py --json

CI：``static-analysis`` 作业（见 ``.github/workflows/pr-checks.yml``）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = ROOT / "frontend" / "src"

# 错误对象的常见变量名
_ERROR_VARS = r"(?:err|error|e|ex|exception|axiosErr|apiError)"
# 直接取 .message
_RAW_MESSAGE = rf"\b{_ERROR_VARS}\s*(?:\?\.)?\.\s*message\b"

# 面向用户的提示调用：抓调用起点，再在其后的实参窗口里找 raw message
_ALERT_CALL = re.compile(
    r"(?:ElMessage|ElNotification|ElMessageBox)\s*\.\s*(?:error|warning|info|alert)\s*\("
    r"|\bnotify\s*\(\s*\{"
)

# 这些文件是实现层（负责把技术错误翻译成中文），允许读 .message
_ALLOWED_FILES = {
    "frontend/src/utils/getErrorMessage.ts",
    "frontend/src/utils/errorHandler.ts",
    "frontend/src/api/request.ts",
}

# 单条提示调用最多向后看多少字符找 raw message（跨行模板串通常远小于此）
_LOOKAHEAD = 400


def _strip_comments(text: str) -> str:
    """去掉注释内容，但**保留换行**，使报告的行号与源文件一致。"""
    def blank(match: re.Match) -> str:
        # 把注释内容换成等长空白（保留 \n），既不误判又不打乱行号
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    text = re.sub(r"(?m)//.*$", blank, text)
    text = re.sub(r"(?ms)<!--.*?-->", blank, text)
    return text


def scan_text(rel_path: str, raw_text: str) -> list[dict]:
    """对一段源码文本做泄漏扫描（纯函数，便于单测）。

    ``rel_path`` 用仓库相对路径（正斜杠），用于报告与豁免判断。
    """
    if rel_path in _ALLOWED_FILES:
        return []
    text = _strip_comments(raw_text)

    findings: list[dict] = []
    for match in _ALERT_CALL.finditer(text):
        window = text[match.start(): match.start() + _LOOKAHEAD]
        hit = re.search(_RAW_MESSAGE, window)
        if not hit:
            continue
        findings.append(
            {
                "file": rel_path,
                "line": text[: match.start()].count("\n") + 1,
                "snippet": _first_line(window, hit.start()),
            }
        )
    return findings


def scan_file(path: Path) -> list[dict]:
    """返回该文件的泄漏点列表。"""
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(rel, raw)


def _first_line(window: str, offset: int) -> str:
    """取命中位置所在行的可读片段（用于报错定位）。"""
    head = window[:offset]
    line_start = head.rfind("\n") + 1
    line_end = window.find("\n", offset)
    if line_end == -1:
        line_end = min(len(window), offset + 120)
    return window[line_start:line_end].strip()[:160]


def collect() -> list[dict]:
    findings: list[dict] = []
    if not FRONTEND_SRC.exists():
        return findings
    for pattern in ("*.ts", "*.vue", "*.tsx"):
        for path in sorted(FRONTEND_SRC.rglob(pattern)):
            if path.name.endswith((".test.ts", ".spec.ts")):
                continue
            findings.extend(scan_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="禁止把 axios 技术原文展示给用户")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    findings = collect()

    if args.json:
        print(json.dumps({"leaks": findings}, ensure_ascii=False, indent=2))
    elif findings:
        print(f"[FAIL] 发现 {len(findings)} 处直接展示 error.message（应改用 getErrorMessage）:")
        for item in findings:
            print(f"    {item['file']}:{item['line']}  {item['snippet']}")
        print()
        print("  修法：import { getErrorMessage } from '@/utils/getErrorMessage'")
        print("        然后 ElMessage.error(getErrorMessage(error, '操作失败'))")
    else:
        print("[OK] 没有把 axios 技术原文直接展示给用户的调用点")

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
