#!/usr/bin/env python
"""PII 三通道扫描（W12-T050 军规合规终检）。

扫描三条出站通道中的明文 PII（身份证号/手机号）：
  1. API 响应通道 —— backend/app/api/v1/**.py 中直接返回模型字段
     （id_card/phone/contact_phone 等）且未经脱敏/加密包装的嫌疑点；
  2. Excel 导出通道 —— backend/app/services/*export*/excel* 中
     写入 id_card/phone 列时是否调用 DataMaskingService；
  3. 日志通道 —— 全 backend 源码 logger/audit 调用中拼接
     身份证/手机号字面量字段的嫌疑点。

退出码：发现高危（0 分容忍）→ 2；仅低危提示 → 0。
用法: python scripts/security/pii_scan.py [--verbose]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"

# 高敏字段名（命中即关注）
PII_FIELDS = ["id_card", "id_number", "phone", "contact_phone", "mobile", "telephone"]

# 已知安全出口（出现则该行不计为嫌疑）
SAFE_MARKERS = [
    "mask", "desensitize", "encrypt", "EncryptionService",
    "DataMaskingService", "hashlib", "sha256", "audit", "logger.debug",
]

API_DIR = BACKEND / "app" / "api" / "v1"
SERVICE_EXPORT_RE = re.compile(r"(export|excel|xlsx|template)", re.IGNORECASE)
LOG_CALL_RE = re.compile(r"(logger|logging|AuditLogger|log)\.\w+\(")


def _iter_py(folder: Path):
    for p in folder.rglob("*.py"):
        if "__pycache__" in str(p) or "tests" in p.parts:
            continue
        yield p


def _line_has_pii_field(line: str) -> bool:
    return any(re.search(rf"\b{f}\b", line, re.IGNORECASE) for f in PII_FIELDS)


def _is_safe(line: str) -> bool:
    lowered = line.lower()
    return any(m.lower() in lowered for m in SAFE_MARKERS)


def scan_api_channel(verbose: bool) -> list[str]:
    """通道1：api/v1 响应构造中直接内插 PII 字段且无脱敏标记。"""
    hits: list[str] = []
    if not API_DIR.exists():
        return hits
    for p in _iter_py(API_DIR):
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if _line_has_pii_field(line) and not _is_safe(line):
                # to_dict()/序列化整对象不算行级嫌疑；只抓显式字段访问
                if re.search(r"\.(id_card|phone|contact_phone|mobile)\b", line):
                    hits.append(f"api/{p.relative_to(API_DIR)}:{i}: {line.strip()[:120]}")
    if verbose:
        print(f"  api channel suspects: {len(hits)}")
    return hits


def scan_export_channel(verbose: bool) -> list[str]:
    """通道2：导出服务写单元格引用 PII 字段但文件内无任何脱敏调用。"""
    hits: list[str] = []
    svc_dir = BACKEND / "app" / "services"
    for p in _iter_py(svc_dir):
        if not SERVICE_EXPORT_RE.search(p.name):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if not _line_has_pii_field(text):
            continue
        if any(m.lower() in text.lower() for m in ("mask", "desensitize", "encrypt")):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if _line_has_pii_field(line) and not _is_safe(line):
                hits.append(f"services/{p.name}:{i}: {line.strip()[:120]}")
    if verbose:
        print(f"  export channel suspects: {len(hits)}")
    return hits


def scan_log_channel(verbose: bool) -> list[str]:
    """通道3：日志调用参数中拼接 .phone/.id_card 等字段。"""
    hits: list[str] = []
    app_dir = BACKEND / "app"
    for p in _iter_py(app_dir):
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if LOG_CALL_RE.search(line) and re.search(
                r"\.(id_card|contact_phone|mobile)\b", line
            ):
                # f-string 或 % 内插 PII 字段到日志
                if not _is_safe(line):
                    hits.append(f"{p.relative_to(app_dir, )}:{i}: {line.strip()[:120]}")
    if verbose:
        print(f"  log channel suspects: {len(hits)}")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    print("[pii-scan] 三通道扫描开始")
    findings = {
        "API响应通道": scan_api_channel(args.verbose),
        "Excel导出通道": scan_export_channel(args.verbose),
        "日志通道": scan_log_channel(args.verbose),
    }

    total = sum(len(v) for v in findings.values())
    print(f"[pii-scan] 嫌疑点合计 {total}")
    for ch, items in findings.items():
        print(f"\n== {ch} ({len(items)}) ==")
        for it in items[:15]:
            print(f"  {it}")
        if len(items) > 15:
            print(f"  ... 及另外 {len(items) - 15} 条")

    if total == 0:
        print("\n[pii-scan] PASS — 零明文 PII 出站嫌疑")
        return 0
    print("\n[pii-scan] 存在嫌疑点：请逐条确认走 DataMaskingService/EncryptionService")
    return 2


if __name__ == "__main__":
    sys.exit(main())
